from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

objetivo_bp = Blueprint("objetivo", __name__, url_prefix="/objetivos")


@objetivo_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def listar_objetivos():
    empresa_id = session["empresa_id"]
    hoy = date.today()

    usuario_id = request.args.get("usuario_id", "")
    rol_id = request.args.get("rol_id", "")
    mes = request.args.get("mes") or str(hoy.month)
    anio = request.args.get("anio") or str(hoy.year)

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, apellido
        FROM usuarios
        WHERE empresa_id = %s AND activo = 1
        ORDER BY apellido, nombre
    """, (empresa_id,))
    empleados = cur.fetchall()

    cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
    roles = cur.fetchall()

    query = """
        SELECT
            o.id, o.titulo, o.descripcion, o.monto_bonus, o.estado,
            o.mes, o.anio, u.nombre, u.apellido, r.nombre
        FROM objetivos o
        LEFT JOIN usuarios u ON o.usuario_id = u.id
        LEFT JOIN roles r ON o.rol_id = r.id
        WHERE o.empresa_id = %s
        AND o.mes = %s AND o.anio = %s
    """
    params = [empresa_id, mes, anio]

    if usuario_id:
        query += " AND o.usuario_id = %s"
        params.append(usuario_id)

    if rol_id:
        query += " AND o.rol_id = %s"
        params.append(rol_id)

    query += " ORDER BY o.estado ASC, o.id DESC"

    cur.execute(query, params)
    objetivos = cur.fetchall()

    cur.close()

    return render_template(
        "objetivos/listar_objetivos.html",
        objetivos=objetivos,
        empleados=empleados,
        roles=roles,
        filtros={
            "usuario_id": usuario_id,
            "rol_id": rol_id,
            "mes": mes,
            "anio": anio
        }
    )


@objetivo_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_objetivo():
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        usuario_id = request.form.get("usuario_id") or None
        rol_id = request.form.get("rol_id") or None
        titulo = request.form["titulo"]
        descripcion = request.form.get("descripcion", "")
        monto_bonus = request.form.get("monto_bonus") or 0
        mes = request.form["mes"]
        anio = request.form["anio"]

        if not usuario_id and not rol_id:
            flash("Elegí un empleado puntual o un sector (rol) para el objetivo.", "danger")
            cur.close()
            return redirect(url_for("objetivo.crear_objetivo"))

        try:
            cur.execute("""
                INSERT INTO objetivos (
                    empresa_id, usuario_id, rol_id, titulo, descripcion,
                    monto_bonus, mes, anio
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                empresa_id, usuario_id, rol_id, titulo, descripcion,
                monto_bonus, mes, anio
            ))

            mysql.connection.commit()
            flash("Objetivo creado correctamente.", "success")
            return redirect(url_for("objetivo.listar_objetivos"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear el objetivo: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("""
            SELECT id, nombre, apellido
            FROM usuarios
            WHERE empresa_id = %s AND activo = 1
            ORDER BY apellido, nombre
        """, (empresa_id,))
        empleados = cur.fetchall()

        cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
        roles = cur.fetchall()

        cur.close()

        hoy = date.today()

        return render_template(
            "objetivos/crear_objetivo.html",
            empleados=empleados,
            roles=roles,
            mes_actual=hoy.month,
            anio_actual=hoy.year
        )


@objetivo_bp.route("/marcar/<int:id>/<estado>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def marcar_objetivo(id, estado):
    empresa_id = session["empresa_id"]

    if estado not in ("pendiente", "cumplido"):
        flash("Estado inválido.", "danger")
        return redirect(url_for("objetivo.listar_objetivos"))

    cur = mysql.connection.cursor()

    if estado == "cumplido":
        cur.execute("""
            UPDATE objetivos
            SET estado = %s, fecha_cumplido = NOW()
            WHERE id = %s AND empresa_id = %s
        """, (estado, id, empresa_id))
    else:
        cur.execute("""
            UPDATE objetivos
            SET estado = %s, fecha_cumplido = NULL
            WHERE id = %s AND empresa_id = %s
        """, (estado, id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Objetivo actualizado correctamente.", "success")
    return redirect(url_for("objetivo.listar_objetivos"))


@objetivo_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def eliminar_objetivo(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM objetivos WHERE id = %s AND empresa_id = %s", (id, empresa_id))
    mysql.connection.commit()
    cur.close()

    flash("Objetivo eliminado.", "success")
    return redirect(url_for("objetivo.listar_objetivos"))
