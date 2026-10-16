from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

ayuda_economica_bp = Blueprint("ayuda_economica", __name__, url_prefix="/ayudas-economicas")


@ayuda_economica_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def listar_ayudas():
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            a.id, a.fecha, u.nombre, u.apellido, a.monto, a.moneda, a.motivo
        FROM ayudas_economicas a
        INNER JOIN usuarios u ON a.usuario_id = u.id
        WHERE a.empresa_id = %s
        ORDER BY a.fecha DESC
        LIMIT 100
    """, (empresa_id,))
    ayudas = cur.fetchall()

    cur.close()

    return render_template(
        "ayudas_economicas/listar_ayudas.html",
        ayudas=ayudas
    )


@ayuda_economica_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_ayuda():
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        usuario_id = request.form["usuario_id"]
        monto = request.form["monto"]
        moneda = "USD"
        motivo = request.form.get("motivo", "")

        try:
            cur.execute("""
                INSERT INTO ayudas_economicas (
                    empresa_id, usuario_id, monto, moneda, motivo
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (empresa_id, usuario_id, monto, moneda, motivo))

            mysql.connection.commit()
            flash("Ayuda económica registrada correctamente.", "success")
            return redirect(url_for("ayuda_economica.listar_ayudas"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al registrar la ayuda: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("""
            SELECT u.id, u.nombre, u.apellido, u.modo_estudiante
            FROM usuarios u
            WHERE u.empresa_id = %s AND u.activo = 1
            ORDER BY u.modo_estudiante DESC, u.apellido, u.nombre
        """, (empresa_id,))
        empleados = cur.fetchall()

        cur.close()

        return render_template(
            "ayudas_economicas/crear_ayuda.html",
            empleados=empleados
        )
