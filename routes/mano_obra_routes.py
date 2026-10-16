from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

mano_obra_bp = Blueprint("mano_obra", __name__, url_prefix="/mano-obra")


@mano_obra_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Tecnico")
def listar_mano_obra():
    empresa_id = session["empresa_id"]

    nombre = request.args.get("nombre", "")
    estado = request.args.get("estado", "")
    buscar = request.args.get("buscar", "")

    trabajos = []

    cur = mysql.connection.cursor()

    if buscar == "1":
        query = """
            SELECT id, nombre, descripcion, precio_usd, tiempo_estimado, activo
            FROM mano_obra
            WHERE empresa_id = %s
        """
        params = [empresa_id]

        if nombre:
            query += " AND nombre LIKE %s"
            params.append(f"%{nombre}%")

        if estado != "":
            query += " AND activo = %s"
            params.append(estado)

        query += " ORDER BY nombre ASC LIMIT 50"

        cur.execute(query, params)
        trabajos = cur.fetchall()

    cur.close()

    return render_template(
        "mano_obra/listar_mano_obra.html",
        trabajos=trabajos,
        filtros={
            "nombre": nombre,
            "estado": estado,
            "buscar": buscar
        }
    )


@mano_obra_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_mano_obra():
    empresa_id = session["empresa_id"]

    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        precio_usd = request.form["precio"] or 0
        tiempo_estimado = request.form["tiempo_estimado"]

        cur = mysql.connection.cursor()

        try:
            cur.execute("""
                INSERT INTO mano_obra (
                    empresa_id, nombre, descripcion, precio_usd, tiempo_estimado, activo
                )
                VALUES (%s, %s, %s, %s, %s, 1)
            """, (
                empresa_id, nombre, descripcion, precio_usd, tiempo_estimado
            ))

            mysql.connection.commit()
            flash("Mano de obra creada correctamente.", "success")
            return redirect(url_for("mano_obra.listar_mano_obra"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear mano de obra: {e}", "danger")

        finally:
            cur.close()

    return render_template("mano_obra/crear_mano_obra.html")


@mano_obra_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def editar_mano_obra(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        precio_usd = request.form["precio"] or 0
        tiempo_estimado = request.form["tiempo_estimado"]

        try:
            cur.execute("""
                UPDATE mano_obra
                SET nombre=%s, descripcion=%s, precio_usd=%s, tiempo_estimado=%s
                WHERE id=%s AND empresa_id=%s
            """, (
                nombre, descripcion, precio_usd, tiempo_estimado,
                id, empresa_id
            ))

            mysql.connection.commit()
            flash("Mano de obra actualizada correctamente.", "success")
            return redirect(url_for("mano_obra.listar_mano_obra"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar mano de obra: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT id, nombre, descripcion, precio_usd, tiempo_estimado
        FROM mano_obra
        WHERE id=%s AND empresa_id=%s
    """, (id, empresa_id))

    trabajo = cur.fetchone()
    cur.close()

    if not trabajo:
        flash("Mano de obra no encontrada.", "danger")
        return redirect(url_for("mano_obra.listar_mano_obra"))

    return render_template(
        "mano_obra/editar_mano_obra.html",
        trabajo=trabajo
    )


@mano_obra_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def eliminar_mano_obra(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE mano_obra
        SET activo = 0
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Mano de obra dada de baja correctamente.", "success")
    return redirect(url_for("mano_obra.listar_mano_obra"))