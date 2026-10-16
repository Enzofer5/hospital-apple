import os
import uuid
import base64
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from extensions import mysql
from utils.email_utils import enviar_email

firma_bp = Blueprint("firma", __name__, url_prefix="/firma")


def guardar_firma_base64(firma_base64, carpeta="firmas"):
    if not firma_base64:
        return None

    if "," in firma_base64:
        firma_base64 = firma_base64.split(",")[1]

    nombre_archivo = f"firma_{uuid.uuid4().hex}.png"

    carpeta_destino = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        carpeta
    )

    os.makedirs(carpeta_destino, exist_ok=True)

    ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

    with open(ruta_completa, "wb") as f:
        f.write(base64.b64decode(firma_base64))

    return f"uploads/{carpeta}/{nombre_archivo}"


def crear_link_firma(token):
    return url_for("firma.firmar_documento", token=token, _external=True)


def enviar_mail_firma(email_cliente, nombre_cliente, tipo_documento, link_firma, empresa_id):
    if not email_cliente:
        return False

    asunto = "Solicitud de firma digital"

    mensaje = f"""
    <h2>Solicitud de firma digital</h2>

    <p>Hola {nombre_cliente},</p>

    <p>Tenés un documento pendiente de firma correspondiente a una <strong>{tipo_documento}</strong>.</p>

    <p>Para firmarlo, ingresá al siguiente enlace:</p>

    <p>
        <a href="{link_firma}" target="_blank"
           style="background:#2563eb;color:white;padding:12px 18px;text-decoration:none;border-radius:8px;">
            Firmar documento
        </a>
    </p>

    <p>Este enlace estará disponible por 7 días.</p>

    <br>

    <p>Muchas gracias.</p>
    """

    return enviar_email(email_cliente, asunto, mensaje, empresa_id)


@firma_bp.route("/solicitar/reparacion/<int:equipo_id>")
def solicitar_firma_reparacion(equipo_id):
    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT 
                e.id,
                e.empresa_id,
                e.cliente_id,
                c.email,
                c.nombre,
                c.apellido
            FROM equipos_reparacion e
            INNER JOIN clientes c ON e.cliente_id = c.id
            WHERE e.id = %s
        """, (equipo_id,))

        reparacion = cur.fetchone()

        if not reparacion:
            flash("Reparación no encontrada.", "danger")
            return redirect(url_for("reparacion.listar_reparaciones"))

        token = uuid.uuid4().hex
        vencimiento = datetime.now() + timedelta(days=7)

        cur.execute("""
            INSERT INTO solicitudes_firma (
                empresa_id, cliente_id, equipo_id, tipo, token,
                estado, fecha_envio, fecha_vencimiento
            )
            VALUES (%s, %s, %s, 'reparacion', %s, 'pendiente', NOW(), %s)
        """, (
            reparacion[1],
            reparacion[2],
            equipo_id,
            token,
            vencimiento
        ))

        cur.execute("""
            UPDATE equipos_reparacion
            SET token_firma = %s,
                firma_estado = 'pendiente'
            WHERE id = %s
        """, (token, equipo_id))

        mysql.connection.commit()

        link_firma = crear_link_firma(token)
        nombre_cliente = f"{reparacion[4]} {reparacion[5]}"

        email_enviado = enviar_mail_firma(
            reparacion[3],
            nombre_cliente,
            "reparación",
            link_firma,
            reparacion[1]
        )

        if email_enviado:
            flash("Solicitud de firma generada y enviada por email.", "success")
        else:
            flash("Solicitud generada, pero no se pudo enviar el email. Podés abrir el enlace manualmente.", "warning")

        return redirect(url_for("reparacion.detalle_reparacion", id=equipo_id))

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al solicitar firma: {e}", "danger")
        return redirect(url_for("reparacion.detalle_reparacion", id=equipo_id))

    finally:
        cur.close()


@firma_bp.route("/solicitar/venta/<int:venta_id>")
def solicitar_firma_venta(venta_id):
    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT 
                v.id,
                v.empresa_id,
                v.cliente_id,
                c.email,
                c.nombre,
                c.apellido
            FROM ventas v
            INNER JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = %s
        """, (venta_id,))

        venta = cur.fetchone()

        if not venta:
            flash("Venta no encontrada.", "danger")
            return redirect(url_for("venta.listar_ventas"))

        token = uuid.uuid4().hex
        vencimiento = datetime.now() + timedelta(days=7)

        cur.execute("""
            INSERT INTO solicitudes_firma (
                empresa_id, cliente_id, venta_id, tipo, token,
                estado, fecha_envio, fecha_vencimiento
            )
            VALUES (%s, %s, %s, 'venta', %s, 'pendiente', NOW(), %s)
        """, (
            venta[1],
            venta[2],
            venta_id,
            token,
            vencimiento
        ))

        cur.execute("""
            UPDATE ventas
            SET token_firma = %s,
                firma_estado = 'pendiente'
            WHERE id = %s
        """, (token, venta_id))

        mysql.connection.commit()

        link_firma = crear_link_firma(token)
        nombre_cliente = f"{venta[4]} {venta[5]}"

        email_enviado = enviar_mail_firma(
            venta[3],
            nombre_cliente,
            "venta",
            link_firma,
            venta[1]
        )

        if email_enviado:
            flash("Solicitud de firma para venta generada y enviada por email.", "success")
        else:
            flash("Solicitud generada, pero no se pudo enviar el email. Podés abrir el enlace manualmente.", "warning")

        return redirect(url_for("venta.detalle_venta", id=venta_id))

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al solicitar firma de venta: {e}", "danger")
        return redirect(url_for("venta.detalle_venta", id=venta_id))

    finally:
        cur.close()


@firma_bp.route("/firmar/<token>", methods=["GET", "POST"])
def firmar_documento(token):
    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT 
                sf.id,
                sf.tipo,
                sf.venta_id,
                sf.equipo_id,
                sf.estado,
                sf.fecha_vencimiento,
                c.nombre,
                c.apellido,
                c.dni
            FROM solicitudes_firma sf
            INNER JOIN clientes c ON sf.cliente_id = c.id
            WHERE sf.token = %s
            LIMIT 1
        """, (token,))

        solicitud = cur.fetchone()

        if not solicitud:
            return "Solicitud de firma no encontrada"

        if solicitud[4] == "firmado":
            return "Este documento ya fue firmado."

        if solicitud[5] and datetime.now() > solicitud[5]:
            cur.execute("""
                UPDATE solicitudes_firma
                SET estado = 'vencido'
                WHERE id = %s
            """, (solicitud[0],))

            mysql.connection.commit()
            return "El enlace de firma venció."

        if request.method == "POST":
            firma_base64 = request.form["firma"]
            ruta_firma = guardar_firma_base64(firma_base64)

            cur.execute("""
                UPDATE solicitudes_firma
                SET estado='firmado',
                    firma_imagen=%s,
                    fecha_firma=NOW()
                WHERE id=%s
            """, (ruta_firma, solicitud[0]))

            if solicitud[1] == "reparacion":
                cur.execute("""
                    UPDATE equipos_reparacion
                    SET firma_cliente=%s,
                        firma_estado='firmado',
                        fecha_firma=NOW()
                    WHERE id=%s
                """, (ruta_firma, solicitud[3]))

            if solicitud[1] == "venta":
                cur.execute("""
                    UPDATE ventas
                    SET firma_cliente=%s,
                        firma_estado='firmado',
                        fecha_firma=NOW()
                    WHERE id=%s
                """, (ruta_firma, solicitud[2]))

            mysql.connection.commit()

            return render_template("firmas/firma_exitosa.html")

        return render_template(
            "firmas/firmar_documento.html",
            solicitud=solicitud,
            token=token
        )

    except Exception as e:
        mysql.connection.rollback()
        return f"Error al procesar firma: {e}"

    finally:
        cur.close()