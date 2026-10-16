import os
import time
import calendar
from datetime import date, timedelta, datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

servicio_bp = Blueprint("servicio", __name__, url_prefix="/servicios")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic", "heif", "pdf"}


def extension_permitida(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def dia_desde_fecha(fecha_txt):
    """Saca el día del mes (1-31) de una fecha 'YYYY-MM-DD' cargada en el form."""
    return int(fecha_txt.split("-")[2])


def siguiente_vencimiento(fecha_actual, dia_deseado):
    """
    Calcula la fecha de vencimiento del mes siguiente, respetando el día
    fijo del servicio recurrente (ej: siempre el 10). Si ese mes no tiene
    ese día (ej: 31 en febrero), usa el último día disponible.
    """
    if not isinstance(fecha_actual, date):
        fecha_actual = datetime.strptime(str(fecha_actual), "%Y-%m-%d").date()

    mes = fecha_actual.month + 1
    anio = fecha_actual.year
    if mes > 12:
        mes = 1
        anio += 1

    ultimo_dia_mes = calendar.monthrange(anio, mes)[1]
    dia = min(dia_deseado, ultimo_dia_mes)
    return date(anio, mes, dia)


def guardar_foto_factura(foto):
    if foto and foto.filename and extension_permitida(foto.filename):
        filename = secure_filename(foto.filename)
        nombre_unico = f"{int(time.time() * 1000)}_{filename}"

        carpeta = os.path.join(current_app.root_path, "static", "uploads", "servicios")
        os.makedirs(carpeta, exist_ok=True)

        ruta_completa = os.path.join(carpeta, nombre_unico)
        foto.save(ruta_completa)

        return f"uploads/servicios/{nombre_unico}"

    return None


@servicio_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Administracion")
def listar_servicios():
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre, monto, fecha_vencimiento, estado, observacion, es_recurrente
        FROM servicios_empresa
        WHERE empresa_id = %s AND estado = 'pendiente'
        ORDER BY fecha_vencimiento ASC
    """, (empresa_id,))
    filas_pendientes = cur.fetchall()

    cur.execute("""
        SELECT id, nombre, monto, fecha_vencimiento, estado, fecha_pago, foto_factura
        FROM servicios_empresa
        WHERE empresa_id = %s AND estado = 'pagado'
        ORDER BY fecha_pago DESC
        LIMIT 30
    """, (empresa_id,))
    pagados = cur.fetchall()

    cur.close()

    hoy = date.today()
    limite = hoy + timedelta(days=10)

    pendientes = []
    for f in filas_pendientes:
        vencimiento = f[3]
        vencido = bool(vencimiento and vencimiento < hoy)
        por_vencer = bool(vencimiento and hoy <= vencimiento <= limite)

        pendientes.append({
            "id": f[0],
            "nombre": f[1],
            "monto": f[2],
            "fecha_vencimiento": f[3],
            "observacion": f[5],
            "vencido": vencido,
            "por_vencer": por_vencer,
            "es_recurrente": bool(f[6]),
        })

    return render_template(
        "servicios/listar_servicios.html",
        pendientes=pendientes,
        pagados=pagados
    )


@servicio_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Administracion")
def crear_servicio():
    empresa_id = session["empresa_id"]

    if request.method == "POST":
        nombre = request.form["nombre"]
        monto = request.form.get("monto") or None
        fecha_vencimiento = request.form["fecha_vencimiento"]
        observacion = request.form.get("observacion", "")
        es_recurrente = 1 if request.form.get("es_recurrente") else 0
        dia_vencimiento = dia_desde_fecha(fecha_vencimiento) if es_recurrente else None

        cur = mysql.connection.cursor()

        try:
            cur.execute("""
                INSERT INTO servicios_empresa (
                    empresa_id, nombre, monto, fecha_vencimiento, estado, observacion,
                    es_recurrente, dia_vencimiento
                )
                VALUES (%s, %s, %s, %s, 'pendiente', %s, %s, %s)
            """, (
                empresa_id, nombre, monto, fecha_vencimiento, observacion,
                es_recurrente, dia_vencimiento
            ))

            mysql.connection.commit()
            if es_recurrente:
                flash("Servicio cargado correctamente. Va a volver a aparecer automáticamente cada mes.", "success")
            else:
                flash("Servicio cargado correctamente.", "success")
            return redirect(url_for("servicio.listar_servicios"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al cargar el servicio: {e}", "danger")

        finally:
            cur.close()

    return render_template("servicios/crear_servicio.html")


@servicio_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Administracion")
def editar_servicio(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        monto = request.form.get("monto") or None
        fecha_vencimiento = request.form["fecha_vencimiento"]
        observacion = request.form.get("observacion", "")
        es_recurrente = 1 if request.form.get("es_recurrente") else 0
        dia_vencimiento = dia_desde_fecha(fecha_vencimiento) if es_recurrente else None

        try:
            cur.execute("""
                UPDATE servicios_empresa
                SET nombre = %s, monto = %s, fecha_vencimiento = %s, observacion = %s,
                    es_recurrente = %s, dia_vencimiento = %s
                WHERE id = %s AND empresa_id = %s
            """, (
                nombre, monto, fecha_vencimiento, observacion,
                es_recurrente, dia_vencimiento, id, empresa_id
            ))

            mysql.connection.commit()
            flash("Servicio actualizado correctamente.", "success")
            return redirect(url_for("servicio.listar_servicios"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar el servicio: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT id, nombre, monto, fecha_vencimiento, observacion, es_recurrente
        FROM servicios_empresa
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))
    servicio = cur.fetchone()
    cur.close()

    if not servicio:
        flash("Servicio no encontrado.", "danger")
        return redirect(url_for("servicio.listar_servicios"))

    return render_template("servicios/editar_servicio.html", servicio=servicio)


@servicio_bp.route("/marcar-pagado/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Administracion")
def marcar_pagado(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        foto = request.files.get("foto_factura")
        ruta_foto = guardar_foto_factura(foto)

        try:
            cur.execute("""
                SELECT nombre, monto, fecha_vencimiento, observacion, estado,
                       es_recurrente, dia_vencimiento
                FROM servicios_empresa
                WHERE id = %s AND empresa_id = %s
            """, (id, empresa_id))
            servicio = cur.fetchone()

            if not servicio:
                flash("Servicio no encontrado.", "danger")
                return redirect(url_for("servicio.listar_servicios"))

            if servicio[4] == "pagado":
                flash("Ese servicio ya estaba marcado como pagado.", "warning")
                return redirect(url_for("servicio.listar_servicios"))

            if ruta_foto:
                cur.execute("""
                    UPDATE servicios_empresa
                    SET estado = 'pagado', fecha_pago = NOW(), foto_factura = %s
                    WHERE id = %s AND empresa_id = %s
                """, (ruta_foto, id, empresa_id))
            else:
                cur.execute("""
                    UPDATE servicios_empresa
                    SET estado = 'pagado', fecha_pago = NOW()
                    WHERE id = %s AND empresa_id = %s
                """, (id, empresa_id))

            # Si es un servicio recurrente (luz, agua, alquiler, etc.), en
            # cuanto se paga ya dejamos cargado el vencimiento del mes que
            # viene, en el mismo día, para que no haya que crearlo de nuevo.
            if servicio[5]:
                nombre, monto, fecha_vencimiento, observacion = servicio[0], servicio[1], servicio[2], servicio[3]
                dia = servicio[6] or dia_desde_fecha(str(fecha_vencimiento))
                proxima_fecha = siguiente_vencimiento(fecha_vencimiento, dia)

                cur.execute("""
                    INSERT INTO servicios_empresa (
                        empresa_id, nombre, monto, fecha_vencimiento, estado,
                        observacion, es_recurrente, dia_vencimiento
                    )
                    VALUES (%s, %s, %s, %s, 'pendiente', %s, 1, %s)
                """, (empresa_id, nombre, monto, proxima_fecha, observacion, dia))

            mysql.connection.commit()

            if servicio[5]:
                flash(
                    f"Pago registrado. Como es recurrente, ya dejamos cargado el próximo "
                    f"vencimiento ({proxima_fecha.strftime('%d/%m/%Y')}) en Pendientes de pago.",
                    "success"
                )
            else:
                flash("Servicio marcado como pagado.", "success")

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al marcar el servicio como pagado: {e}", "danger")

        finally:
            cur.close()

        return redirect(url_for("servicio.listar_servicios"))

    cur.execute("""
        SELECT id, nombre, monto, fecha_vencimiento
        FROM servicios_empresa
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))
    servicio = cur.fetchone()
    cur.close()

    if not servicio:
        flash("Servicio no encontrado.", "danger")
        return redirect(url_for("servicio.listar_servicios"))

    return render_template("servicios/marcar_pagado.html", servicio=servicio)


@servicio_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Administracion")
def eliminar_servicio(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            DELETE FROM servicios_empresa
            WHERE id = %s AND empresa_id = %s
        """, (id, empresa_id))

        mysql.connection.commit()
        flash("Servicio eliminado.", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al eliminar el servicio: {e}", "danger")

    finally:
        cur.close()

    return redirect(url_for("servicio.listar_servicios"))
