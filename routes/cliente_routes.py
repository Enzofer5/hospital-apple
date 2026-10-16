from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

cliente_bp = Blueprint("cliente", __name__, url_prefix="/clientes")


@cliente_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Vendedor")
def listar_clientes():
    empresa_id = session["empresa_id"]

    nombre = request.args.get("nombre", "")
    dni = request.args.get("dni", "")
    telefono = request.args.get("telefono", "")
    estado = request.args.get("estado", "")
    buscar = request.args.get("buscar", "")

    clientes = []
    cur = mysql.connection.cursor()

    if buscar == "1":
        query = """
            SELECT id, nombre, apellido, dni, email, telefono,
                   fecha_nacimiento, direccion, localidad, activo
            FROM clientes
            WHERE empresa_id = %s
        """
        params = [empresa_id]

        if nombre:
            query += " AND (nombre LIKE %s OR apellido LIKE %s)"
            params.extend([f"%{nombre}%", f"%{nombre}%"])

        if dni:
            query += " AND dni LIKE %s"
            params.append(f"%{dni}%")

        if telefono:
            query += " AND telefono LIKE %s"
            params.append(f"%{telefono}%")

        if estado != "":
            query += " AND activo = %s"
            params.append(estado)

        query += " ORDER BY apellido ASC LIMIT 50"

        cur.execute(query, params)
        clientes = cur.fetchall()

    cur.close()

    return render_template(
        "clientes/listar_cliente.html",
        clientes=clientes,
        filtros={
            "nombre": nombre,
            "dni": dni,
            "telefono": telefono,
            "estado": estado,
            "buscar": buscar
        }
    )


@cliente_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Vendedor")
def crear_cliente():
    empresa_id = session["empresa_id"]

    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        dni = request.form["dni"]
        email = request.form["email"]
        telefono = request.form["telefono"]
        fecha_nacimiento = request.form["fecha_nacimiento"] or None
        direccion = request.form["direccion"]
        localidad = request.form["localidad"]
        observaciones = request.form["observaciones"]

        cur = mysql.connection.cursor()

        try:
            cur.execute("""
                INSERT INTO clientes (
                    empresa_id, nombre, apellido, dni, email, telefono,
                    fecha_nacimiento, direccion, localidad, observaciones,
                    email_confirmado, activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 1)
            """, (
                empresa_id, nombre, apellido, dni, email, telefono,
                fecha_nacimiento, direccion, localidad, observaciones
            ))

            mysql.connection.commit()
            flash("Cliente creado correctamente.", "success")
            return redirect(url_for("cliente.listar_clientes"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear cliente: {e}", "danger")

        finally:
            cur.close()

    return render_template("clientes/crear_cliente.html")


@cliente_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def editar_cliente(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        dni = request.form["dni"]
        email = request.form["email"]
        telefono = request.form["telefono"]
        fecha_nacimiento = request.form["fecha_nacimiento"] or None
        direccion = request.form["direccion"]
        localidad = request.form["localidad"]
        observaciones = request.form["observaciones"]

        try:
            cur.execute("""
                UPDATE clientes
                SET nombre=%s, apellido=%s, dni=%s, email=%s, telefono=%s,
                    fecha_nacimiento=%s, direccion=%s, localidad=%s,
                    observaciones=%s
                WHERE id=%s AND empresa_id=%s
            """, (
                nombre, apellido, dni, email, telefono,
                fecha_nacimiento, direccion, localidad, observaciones,
                id, empresa_id
            ))

            mysql.connection.commit()
            flash("Cliente actualizado correctamente.", "success")
            return redirect(url_for("cliente.listar_clientes"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar cliente: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT id, nombre, apellido, dni, email, telefono,
               fecha_nacimiento, direccion, localidad, observaciones
        FROM clientes
        WHERE id=%s AND empresa_id=%s
    """, (id, empresa_id))

    cliente = cur.fetchone()
    cur.close()

    if not cliente:
        flash("Cliente no encontrado.", "danger")
        return redirect(url_for("cliente.listar_clientes"))

    return render_template("clientes/editar_cliente.html", cliente=cliente)


@cliente_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def eliminar_cliente(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE clientes
        SET activo = 0
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Cliente dado de baja correctamente.", "success")
    return redirect(url_for("cliente.listar_clientes"))