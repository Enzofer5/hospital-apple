from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

proveedor_bp = Blueprint("proveedor", __name__, url_prefix="/proveedores")


@proveedor_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def listar_proveedores():
    empresa_id = session["empresa_id"]

    nombre = request.args.get("nombre", "")
    cuit = request.args.get("cuit", "")
    telefono = request.args.get("telefono", "")
    estado = request.args.get("estado", "")
    buscar = request.args.get("buscar", "")

    proveedores = []

    cur = mysql.connection.cursor()

    if buscar == "1":
        query = """
            SELECT id, nombre, cuit, email, telefono, direccion, activo
            FROM proveedores
            WHERE empresa_id = %s
        """
        params = [empresa_id]

        if nombre:
            query += " AND nombre LIKE %s"
            params.append(f"%{nombre}%")

        if cuit:
            query += " AND cuit LIKE %s"
            params.append(f"%{cuit}%")

        if telefono:
            query += " AND telefono LIKE %s"
            params.append(f"%{telefono}%")

        if estado != "":
            query += " AND activo = %s"
            params.append(estado)

        query += " ORDER BY nombre ASC LIMIT 50"

        cur.execute(query, params)
        proveedores = cur.fetchall()

    cur.close()

    return render_template(
        "proveedores/listar_proveedor.html",
        proveedores=proveedores,
        filtros={
            "nombre": nombre,
            "cuit": cuit,
            "telefono": telefono,
            "estado": estado,
            "buscar": buscar
        }
    )


@proveedor_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_proveedor():
    empresa_id = session["empresa_id"]

    if request.method == "POST":
        nombre = request.form["nombre"]
        cuit = request.form["cuit"]
        email = request.form["email"]
        telefono = request.form["telefono"]
        direccion = request.form["direccion"]

        cur = mysql.connection.cursor()

        try:
            cur.execute("""
                INSERT INTO proveedores (
                    empresa_id, nombre, cuit, email, telefono, direccion, activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (
                empresa_id, nombre, cuit, email, telefono, direccion
            ))

            mysql.connection.commit()
            flash("Proveedor creado correctamente.", "success")
            return redirect(url_for("proveedor.listar_proveedores"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear proveedor: {e}", "danger")

        finally:
            cur.close()

    return render_template("proveedores/crear_proveedor.html")


@proveedor_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def editar_proveedor(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        cuit = request.form["cuit"]
        email = request.form["email"]
        telefono = request.form["telefono"]
        direccion = request.form["direccion"]

        try:
            cur.execute("""
                UPDATE proveedores
                SET nombre=%s, cuit=%s, email=%s, telefono=%s, direccion=%s
                WHERE id=%s AND empresa_id=%s
            """, (
                nombre, cuit, email, telefono, direccion,
                id, empresa_id
            ))

            mysql.connection.commit()
            flash("Proveedor actualizado correctamente.", "success")
            return redirect(url_for("proveedor.listar_proveedores"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar proveedor: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT id, nombre, cuit, email, telefono, direccion
        FROM proveedores
        WHERE id=%s AND empresa_id=%s
    """, (id, empresa_id))

    proveedor = cur.fetchone()
    cur.close()

    if not proveedor:
        flash("Proveedor no encontrado.", "danger")
        return redirect(url_for("proveedor.listar_proveedores"))

    return render_template(
        "proveedores/editar_proveedor.html",
        proveedor=proveedor
    )


@proveedor_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def eliminar_proveedor(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE proveedores
        SET activo = 0
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Proveedor dado de baja correctamente.", "success")
    return redirect(url_for("proveedor.listar_proveedores"))