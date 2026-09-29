from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

empleado_bp = Blueprint("empleado", __name__, url_prefix="/empleados")


@empleado_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def listar_empleados():
    empresa_id = session["empresa_id"]

    nombre = request.args.get("nombre", "")
    rol_id = request.args.get("rol_id", "")
    sucursal_id = request.args.get("sucursal_id", "")
    estado = request.args.get("estado", "")
    buscar = request.args.get("buscar", "")

    empleados = []

    cur = mysql.connection.cursor()

    cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
    roles = cur.fetchall()

    cur.execute("""
        SELECT id, nombre
        FROM sucursales
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    sucursales = cur.fetchall()

    # Solo busca si el usuario presiona el botón Buscar
    if buscar == "1":
        query = """
            SELECT
                u.id, u.nombre, u.apellido, u.dni, u.email, u.telefono,
                u.sueldo_usd, u.porcentaje_comision, u.activo,
                r.nombre AS rol,
                s.nombre AS sucursal
            FROM usuarios u
            INNER JOIN roles r ON u.rol_id = r.id
            LEFT JOIN sucursales s ON u.sucursal_id = s.id
            WHERE u.empresa_id = %s
        """

        params = [empresa_id]

        if nombre:
            query += " AND (u.nombre LIKE %s OR u.apellido LIKE %s)"
            params.extend([f"%{nombre}%", f"%{nombre}%"])

        if rol_id:
            query += " AND u.rol_id = %s"
            params.append(rol_id)

        if sucursal_id:
            query += " AND u.sucursal_id = %s"
            params.append(sucursal_id)

        if estado != "":
            query += " AND u.activo = %s"
            params.append(estado)

        query += " ORDER BY u.apellido ASC LIMIT 50"

        cur.execute(query, params)
        empleados = cur.fetchall()

    cur.close()

    return render_template(
        "empleados/listar_empleados.html",
        empleados=empleados,
        roles=roles,
        sucursales=sucursales,
        filtros={
            "nombre": nombre,
            "rol_id": rol_id,
            "sucursal_id": sucursal_id,
            "estado": estado,
            "buscar": buscar
        }
    )


@empleado_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_empleado():
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        dni = request.form["dni"]
        email = request.form["email"]
        telefono = request.form["telefono"]
        password = generate_password_hash(request.form["password"])
        rol_id = request.form["rol_id"]
        sucursal_id = request.form["sucursal_id"]
        sueldo_usd = request.form["sueldo"] or 0
        porcentaje_comision = request.form["porcentaje_comision"] or 0
        modo_estudiante = 1 if request.form.get("modo_estudiante") else 0

        try:
            cur.execute("""
                INSERT INTO usuarios (
                    empresa_id, sucursal_id, rol_id, nombre, apellido, dni,
                    email, password, telefono, sueldo_usd, porcentaje_comision,
                    modo_estudiante, activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """, (
                empresa_id, sucursal_id, rol_id, nombre, apellido, dni,
                email, password, telefono, sueldo_usd, porcentaje_comision,
                modo_estudiante
            ))

            mysql.connection.commit()
            flash("Empleado creado correctamente.", "success")
            return redirect(url_for("empleado.listar_empleados"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear empleado: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
        roles = cur.fetchall()

        cur.execute("""
            SELECT id, nombre
            FROM sucursales
            WHERE empresa_id = %s AND activo = 1
            ORDER BY nombre
        """, (empresa_id,))
        sucursales = cur.fetchall()

        cur.close()

        return render_template(
            "empleados/crear_empleado.html",
            roles=roles,
            sucursales=sucursales
        )


@empleado_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def editar_empleado(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        dni = request.form["dni"]
        email = request.form["email"]
        telefono = request.form["telefono"]
        rol_id = request.form["rol_id"]
        sucursal_id = request.form["sucursal_id"]
        sueldo_usd = request.form["sueldo"] or 0
        porcentaje_comision = request.form["porcentaje_comision"] or 0
        modo_estudiante = 1 if request.form.get("modo_estudiante") else 0

        try:
            cur.execute("""
                UPDATE usuarios
                SET nombre=%s, apellido=%s, dni=%s, email=%s, telefono=%s,
                    rol_id=%s, sucursal_id=%s, sueldo_usd=%s, porcentaje_comision=%s,
                    modo_estudiante=%s
                WHERE id=%s AND empresa_id=%s
            """, (
                nombre, apellido, dni, email, telefono,
                rol_id, sucursal_id, sueldo_usd, porcentaje_comision,
                modo_estudiante, id, empresa_id
            ))

            mysql.connection.commit()
            flash("Empleado actualizado correctamente.", "success")
            return redirect(url_for("empleado.listar_empleados"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar empleado: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("""
            SELECT id, nombre, apellido, dni, email, telefono,
                   rol_id, sucursal_id, sueldo_usd, porcentaje_comision,
                   modo_estudiante
            FROM usuarios
            WHERE id = %s AND empresa_id = %s
        """, (id, empresa_id))
        empleado = cur.fetchone()

        if not empleado:
            cur.close()
            flash("Empleado no encontrado.", "danger")
            return redirect(url_for("empleado.listar_empleados"))

        cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
        roles = cur.fetchall()

        cur.execute("""
            SELECT id, nombre
            FROM sucursales
            WHERE empresa_id = %s AND activo = 1
            ORDER BY nombre
        """, (empresa_id,))
        sucursales = cur.fetchall()

        cur.close()

        return render_template(
            "empleados/editar_empleados.html",
            empleado=empleado,
            roles=roles,
            sucursales=sucursales
        )


@empleado_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def eliminar_empleado(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE usuarios
        SET activo = 0
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Empleado dado de baja correctamente.", "success")
    return redirect(url_for("empleado.listar_empleados"))