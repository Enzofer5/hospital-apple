import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import mysql
from utils.email_utils import enviar_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT 
                u.id, u.nombre, u.apellido, u.password,
                u.empresa_id, u.sucursal_id,
                r.nombre AS rol,
                e.estado AS estado_empresa
            FROM usuarios u
            INNER JOIN roles r ON u.rol_id = r.id
            INNER JOIN empresas e ON u.empresa_id = e.id
            WHERE u.email = %s
            AND u.activo = 1
            LIMIT 1
        """, (email,))

        usuario = cur.fetchone()
        cur.close()

        if usuario:
            if usuario[7] != "activa":
                flash("La empresa no tiene una suscripción activa.", "danger")
                return redirect(url_for("auth.login"))

            if check_password_hash(usuario[3], password):
                session["usuario_id"] = usuario[0]
                session["nombre"] = usuario[1]
                session["apellido"] = usuario[2]
                session["empresa_id"] = usuario[4]
                session["sucursal_id"] = usuario[5]
                session["rol"] = usuario[6]

                return redirect(url_for("dashboard.dashboard"))

        flash("Email o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/crear-dueno", methods=["GET", "POST"])
def crear_dueno():
    # Alta de una empresa nueva con su usuario Dueño. Se puede usar en
    # cualquier momento (no solo la primera vez): así cualquier negocio
    # nuevo puede darse de alta por su cuenta, como corresponde en un
    # sistema pensado para varias empresas por suscripción.
    if request.method == "POST":
        empresa_nombre = request.form["empresa_nombre"]
        empresa_email = request.form["empresa_email"]
        empresa_telefono = request.form["empresa_telefono"]
        empresa_direccion = request.form["empresa_direccion"]

        sucursal_nombre = request.form["sucursal_nombre"]

        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        dni = request.form["dni"]
        email = request.form["email"].strip()
        telefono = request.form["telefono"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        cur = mysql.connection.cursor()

        try:
            cur.execute("SELECT id FROM usuarios WHERE email = %s LIMIT 1", (email,))
            if cur.fetchone():
                flash("Ese email ya está registrado. Iniciá sesión o usá otro email.", "danger")
                cur.close()
                return render_template("auth/crear_dueno.html")

            cur.execute("""
                INSERT INTO empresas(nombre, email, telefono, direccion, estado)
                VALUES (%s, %s, %s, %s, 'activa')
            """, (empresa_nombre, empresa_email, empresa_telefono, empresa_direccion))

            empresa_id = cur.lastrowid

            cur.execute("""
                INSERT INTO sucursales(empresa_id, nombre, direccion, telefono, activo)
                VALUES (%s, %s, %s, %s, 1)
            """, (empresa_id, sucursal_nombre, empresa_direccion, empresa_telefono))

            sucursal_id = cur.lastrowid

            cur.execute("""
                SELECT id FROM roles WHERE nombre = 'Dueño' LIMIT 1
            """)
            rol_dueno = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO usuarios(
                    empresa_id, sucursal_id, rol_id, nombre, apellido, dni,
                    email, password, telefono, sueldo_ars, sueldo_usd, porcentaje_comision, activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, 0, 1)
            """, (
                empresa_id, sucursal_id, rol_dueno, nombre, apellido, dni,
                email, password_hash, telefono
            ))

            mysql.connection.commit()
            flash("Cuenta creada correctamente. Ahora podés iniciar sesión.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear la cuenta: {e}", "danger")
            return render_template("auth/crear_dueno.html")

        finally:
            cur.close()

    return render_template("auth/crear_dueno.html")


@auth_bp.route("/recuperar-password", methods=["GET", "POST"])
def recuperar_password():
    if request.method == "POST":
        email = request.form["email"].strip()

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, nombre, empresa_id
            FROM usuarios
            WHERE email = %s AND activo = 1
            LIMIT 1
        """, (email,))
        usuario = cur.fetchone()

        if usuario:
            token = uuid.uuid4().hex
            vencimiento = datetime.now() + timedelta(hours=1)

            cur.execute("""
                INSERT INTO recuperacion_password (
                    usuario_id, token, fecha_expiracion, usado
                )
                VALUES (%s, %s, %s, 0)
            """, (usuario[0], token, vencimiento))

            mysql.connection.commit()

            link_reset = url_for("auth.resetear_password", token=token, _external=True)

            mensaje = f"""
            <h2>Recuperación de contraseña</h2>
            <p>Hola {usuario[1]},</p>
            <p>Recibimos un pedido para restablecer tu contraseña. Si fuiste vos, ingresá al siguiente enlace:</p>
            <p>
                <a href="{link_reset}" target="_blank"
                   style="background:#2563eb;color:white;padding:12px 18px;text-decoration:none;border-radius:8px;">
                    Restablecer contraseña
                </a>
            </p>
            <p>Este enlace vence en 1 hora. Si vos no pediste esto, podés ignorar el mensaje.</p>
            """

            enviar_email(email, "Recuperación de contraseña", mensaje, usuario[2])

        cur.close()

        flash("Si el email existe en el sistema, te enviamos un enlace para restablecer la contraseña.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/recuperar_password.html")


@auth_bp.route("/resetear-password/<token>", methods=["GET", "POST"])
def resetear_password(token):
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, usuario_id, fecha_expiracion, usado
        FROM recuperacion_password
        WHERE token = %s
        LIMIT 1
    """, (token,))
    solicitud = cur.fetchone()

    if not solicitud:
        cur.close()
        flash("El enlace de recuperación no es válido.", "danger")
        return redirect(url_for("auth.login"))

    if solicitud[3] == 1:
        cur.close()
        flash("Este enlace ya fue usado. Pedí uno nuevo si lo necesitás.", "danger")
        return redirect(url_for("auth.recuperar_password"))

    if datetime.now() > solicitud[2]:
        cur.close()
        flash("Este enlace venció. Pedí uno nuevo.", "danger")
        return redirect(url_for("auth.recuperar_password"))

    if request.method == "POST":
        password = request.form["password"]
        password_confirmar = request.form["password_confirmar"]

        if len(password) < 6:
            flash("La contraseña tiene que tener al menos 6 caracteres.", "danger")
            cur.close()
            return render_template("auth/resetear_password.html", token=token)

        if password != password_confirmar:
            flash("Las contraseñas no coinciden.", "danger")
            cur.close()
            return render_template("auth/resetear_password.html", token=token)

        password_hash = generate_password_hash(password)

        cur.execute("""
            UPDATE usuarios SET password = %s WHERE id = %s
        """, (password_hash, solicitud[1]))

        cur.execute("""
            UPDATE recuperacion_password SET usado = 1 WHERE id = %s
        """, (solicitud[0],))

        mysql.connection.commit()
        cur.close()

        flash("Contraseña actualizada correctamente. Ya podés iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    cur.close()
    return render_template("auth/resetear_password.html", token=token)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))