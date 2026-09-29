import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos
from utils.email_utils import enviar_email

ficha_tecnica_bp = Blueprint("ficha_tecnica", __name__, url_prefix="/notas-tecnicas")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic", "heif"}


def extension_permitida(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_foto_ficha(foto):
    if foto and foto.filename and extension_permitida(foto.filename):
        filename = secure_filename(foto.filename)
        nombre_unico = f"{int(datetime.utcnow().timestamp() * 1000)}_{filename}"

        carpeta = os.path.join(current_app.root_path, "static", "uploads", "fichas_tecnicas")
        os.makedirs(carpeta, exist_ok=True)

        ruta_completa = os.path.join(carpeta, nombre_unico)
        foto.save(ruta_completa)

        return f"uploads/fichas_tecnicas/{nombre_unico}"

    return None


def enviar_mail_ficha_tecnica(email_cliente, nombre_cliente, ficha, empresa_id):
    """
    Manda la nota técnica (diagnóstico, notas y costos) por mail al cliente,
    usando la casilla de correo configurada por la empresa.
    ficha = (id, fecha, diagnostico, notas_tecnicas, moneda, costo_mano_obra,
             costo_repuestos, total, ...)
    """
    if not email_cliente:
        return False

    asunto = "Nota técnica de tu reparación"

    diagnostico = ficha[2] or "Sin diagnóstico cargado."
    notas = ficha[3] or "Sin notas adicionales."
    moneda = ficha[4]

    mensaje = f"""
    <h2>Nota técnica de tu reparación</h2>

    <p>Hola {nombre_cliente},</p>

    <p>Te compartimos el detalle de la revisión técnica de tu equipo:</p>

    <p><strong>Diagnóstico:</strong><br>{diagnostico}</p>

    <p><strong>Notas técnicas:</strong><br>{notas}</p>

    <p>
        <strong>Mano de obra:</strong> {moneda} {ficha[5]}<br>
        <strong>Repuestos:</strong> {moneda} {ficha[6]}<br>
        <strong>Total:</strong> {moneda} {ficha[7]}
    </p>

    <br>

    <p>Cualquier consulta, respondé este mismo mail.</p>
    """

    return enviar_email(email_cliente, asunto, mensaje, empresa_id)


@ficha_tecnica_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def listar_fichas():
    empresa_id = session["empresa_id"]

    cliente = request.args.get("cliente", "")
    tecnico_id = request.args.get("tecnico_id", "")
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    buscar = request.args.get("buscar", "")

    fichas = []
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT u.id, u.nombre, u.apellido
        FROM usuarios u
        INNER JOIN roles r ON u.rol_id = r.id
        WHERE u.empresa_id = %s
        AND r.nombre = 'Tecnico'
        AND u.activo = 1
        ORDER BY u.apellido, u.nombre
    """, (empresa_id,))
    tecnicos = cur.fetchall()

    if buscar == "1":
        query = """
            SELECT
                f.id, f.fecha, c.nombre, c.apellido,
                e.marca, e.modelo, u.nombre, u.apellido,
                f.diagnostico, f.moneda, f.total
            FROM fichas_tecnicas f
            INNER JOIN equipos_reparacion e ON f.equipo_id = e.id
            INNER JOIN clientes c ON e.cliente_id = c.id
            LEFT JOIN usuarios u ON f.tecnico_id = u.id
            WHERE e.empresa_id = %s
        """
        params = [empresa_id]

        if cliente:
            query += " AND (c.nombre LIKE %s OR c.apellido LIKE %s OR c.dni LIKE %s)"
            params.extend([f"%{cliente}%", f"%{cliente}%", f"%{cliente}%"])

        if tecnico_id:
            query += " AND f.tecnico_id = %s"
            params.append(tecnico_id)

        if fecha_desde:
            query += " AND DATE(f.fecha) >= %s"
            params.append(fecha_desde)

        if fecha_hasta:
            query += " AND DATE(f.fecha) <= %s"
            params.append(fecha_hasta)

        query += " ORDER BY f.fecha DESC LIMIT 100"

        cur.execute(query, params)
        fichas = cur.fetchall()

    cur.close()

    return render_template(
        "notas_tecnicas/listar_fichas.html",
        fichas=fichas,
        tecnicos=tecnicos,
        filtros={
            "cliente": cliente,
            "tecnico_id": tecnico_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "buscar": buscar
        }
    )


@ficha_tecnica_bp.route("/crear/<int:equipo_id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Tecnico")
def crear_ficha(equipo_id):
    empresa_id = session["empresa_id"]
    usuario_id = session["usuario_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT e.id, c.nombre, c.apellido, e.marca, e.modelo, e.nro_serie
        FROM equipos_reparacion e
        INNER JOIN clientes c ON e.cliente_id = c.id
        WHERE e.id = %s AND e.empresa_id = %s
    """, (equipo_id, empresa_id))
    equipo = cur.fetchone()

    if not equipo:
        cur.close()
        flash("Reparación no encontrada.", "danger")
        return redirect(url_for("reparacion.listar_reparaciones"))

    if request.method == "POST":
        diagnostico = request.form.get("diagnostico", "")
        notas_tecnicas = request.form.get("notas_tecnicas", "")
        moneda = "USD"
        costo_mano_obra = request.form.get("costo_mano_obra") or 0
        costo_repuestos = request.form.get("costo_repuestos") or 0
        total = float(costo_mano_obra) + float(costo_repuestos)
        fotos = request.files.getlist("fotos[]")

        try:
            cur.execute("""
                INSERT INTO fichas_tecnicas (
                    equipo_id, tecnico_id, diagnostico, notas_tecnicas,
                    moneda, costo_mano_obra, costo_repuestos, total
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                equipo_id, usuario_id, diagnostico, notas_tecnicas,
                moneda, costo_mano_obra, costo_repuestos, total
            ))

            ficha_id = cur.lastrowid

            for foto in fotos:
                ruta = guardar_foto_ficha(foto)
                if ruta:
                    cur.execute("""
                        INSERT INTO fotos_ficha_tecnica (ficha_id, ruta)
                        VALUES (%s, %s)
                    """, (ficha_id, ruta))

                    # La misma foto queda también como foto "después" de la
                    # reparación, para que se vea en el detalle de la reparación.
                    cur.execute("""
                        INSERT INTO fotos_reparacion (equipo_id, tipo, ruta)
                        VALUES (%s, 'despues', %s)
                    """, (equipo_id, ruta))

            mysql.connection.commit()
            flash("Nota técnica creada correctamente.", "success")
            return redirect(url_for("ficha_tecnica.detalle_ficha", id=ficha_id))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear la nota técnica: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.close()
        return render_template("notas_tecnicas/crear_ficha.html", equipo=equipo)


@ficha_tecnica_bp.route("/detalle/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def detalle_ficha(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            f.id, f.fecha, f.diagnostico, f.notas_tecnicas,
            f.moneda, f.costo_mano_obra, f.costo_repuestos, f.total,
            c.nombre, c.apellido, c.dni, e.id, e.marca, e.modelo, e.nro_serie,
            u.nombre, u.apellido, c.email, f.enviado_email
        FROM fichas_tecnicas f
        INNER JOIN equipos_reparacion e ON f.equipo_id = e.id
        INNER JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN usuarios u ON f.tecnico_id = u.id
        WHERE f.id = %s AND e.empresa_id = %s
    """, (id, empresa_id))
    ficha = cur.fetchone()

    if not ficha:
        cur.close()
        flash("Nota técnica no encontrada.", "danger")
        return redirect(url_for("ficha_tecnica.listar_fichas"))

    cur.execute("""
        SELECT id, ruta, fecha
        FROM fotos_ficha_tecnica
        WHERE ficha_id = %s
        ORDER BY fecha ASC
    """, (id,))
    fotos = cur.fetchall()

    cur.close()

    return render_template(
        "notas_tecnicas/detalle_ficha.html",
        ficha=ficha,
        fotos=fotos
    )


@ficha_tecnica_bp.route("/<int:id>/agregar-foto", methods=["POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Tecnico")
def agregar_foto(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT f.id, f.equipo_id
        FROM fichas_tecnicas f
        INNER JOIN equipos_reparacion e ON f.equipo_id = e.id
        WHERE f.id = %s AND e.empresa_id = %s
    """, (id, empresa_id))

    fila_ficha = cur.fetchone()

    if not fila_ficha:
        cur.close()
        flash("Nota técnica no encontrada.", "danger")
        return redirect(url_for("ficha_tecnica.listar_fichas"))

    equipo_id = fila_ficha[1]

    fotos = request.files.getlist("fotos[]")

    try:
        agregadas = 0
        for foto in fotos:
            ruta = guardar_foto_ficha(foto)
            if ruta:
                cur.execute("""
                    INSERT INTO fotos_ficha_tecnica (ficha_id, ruta)
                    VALUES (%s, %s)
                """, (id, ruta))

                cur.execute("""
                    INSERT INTO fotos_reparacion (equipo_id, tipo, ruta)
                    VALUES (%s, 'despues', %s)
                """, (equipo_id, ruta))

                agregadas += 1

        mysql.connection.commit()

        if agregadas:
            flash(f"Se agregaron {agregadas} foto(s) correctamente.", "success")
        else:
            flash("No se seleccionó ninguna foto válida.", "warning")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al agregar fotos: {e}", "danger")

    finally:
        cur.close()

    return redirect(url_for("ficha_tecnica.detalle_ficha", id=id))


@ficha_tecnica_bp.route("/<int:id>/enviar-email")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def enviar_email_ficha(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT
                f.id, f.fecha, f.diagnostico, f.notas_tecnicas,
                f.moneda, f.costo_mano_obra, f.costo_repuestos, f.total,
                c.nombre, c.apellido, c.email
            FROM fichas_tecnicas f
            INNER JOIN equipos_reparacion e ON f.equipo_id = e.id
            INNER JOIN clientes c ON e.cliente_id = c.id
            WHERE f.id = %s AND e.empresa_id = %s
        """, (id, empresa_id))
        ficha = cur.fetchone()

        if not ficha:
            flash("Nota técnica no encontrada.", "danger")
            return redirect(url_for("ficha_tecnica.listar_fichas"))

        email_cliente = ficha[10]
        nombre_cliente = f"{ficha[8]} {ficha[9]}"

        if not email_cliente:
            flash("El cliente no tiene un email cargado. Agregalo en su ficha de Cliente para poder enviarle la nota.", "warning")
            return redirect(url_for("ficha_tecnica.detalle_ficha", id=id))

        enviado = enviar_mail_ficha_tecnica(email_cliente, nombre_cliente, ficha, empresa_id)

        if enviado:
            cur.execute("""
                UPDATE fichas_tecnicas SET enviado_email = 1 WHERE id = %s
            """, (id,))
            mysql.connection.commit()
            flash(f"Nota técnica enviada por email a {email_cliente}.", "success")
        else:
            flash(
                "No se pudo enviar el email. Revisá que la empresa tenga configurado "
                "su email y contraseña de aplicación en Configuración.",
                "danger"
            )

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al enviar la nota técnica por email: {e}", "danger")

    finally:
        cur.close()

    return redirect(url_for("ficha_tecnica.detalle_ficha", id=id))
