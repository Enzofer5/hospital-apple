import os
import time
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")

ALLOWED_LOGO_EXT = {"png", "jpg", "jpeg", "webp"}


def extension_logo_permitida(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXT


def guardar_logo(foto):
    if foto and foto.filename and extension_logo_permitida(foto.filename):
        filename = secure_filename(foto.filename)
        nombre_unico = f"{int(time.time() * 1000)}_{filename}"

        carpeta = os.path.join(current_app.root_path, "static", "uploads", "logos")
        os.makedirs(carpeta, exist_ok=True)

        ruta_completa = os.path.join(carpeta, nombre_unico)
        foto.save(ruta_completa)

        return f"uploads/logos/{nombre_unico}"

    return None


def obtener_meta(cur, empresa_id, concepto):
    cur.execute("""
        SELECT monto FROM metas_empresa
        WHERE empresa_id = %s AND concepto = %s
    """, (empresa_id, concepto))
    fila = cur.fetchone()
    return fila[0] if fila else 0


def guardar_meta(cur, empresa_id, concepto, monto):
    cur.execute("""
        INSERT INTO metas_empresa (empresa_id, concepto, monto)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE monto = VALUES(monto)
    """, (empresa_id, concepto, monto))


@configuracion_bp.route("/", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def configuracion():
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        formulario = request.form.get("formulario")

        if formulario == "meta":
            meta_mensual_negocio = request.form.get("meta_mensual_negocio") or 0

            try:
                guardar_meta(cur, empresa_id, "meta_mensual_negocio", meta_mensual_negocio)
                mysql.connection.commit()
                flash("Configuración guardada correctamente.", "success")

            except Exception as e:
                mysql.connection.rollback()
                flash(f"Error al guardar la configuración: {e}", "danger")

            finally:
                cur.close()

        elif formulario == "email":
            empresa_email = request.form.get("empresa_email", "").strip()
            email_password_app = request.form.get("email_password_app", "").strip()

            try:
                if email_password_app:
                    cur.execute("""
                        UPDATE empresas
                        SET email = %s, email_password_app = %s
                        WHERE id = %s
                    """, (empresa_email, email_password_app, empresa_id))
                else:
                    # Si dejan la contraseña vacía, no la pisamos: solo actualizamos el mail.
                    cur.execute("""
                        UPDATE empresas
                        SET email = %s
                        WHERE id = %s
                    """, (empresa_email, empresa_id))

                mysql.connection.commit()
                flash("Email de la empresa guardado correctamente.", "success")

            except Exception as e:
                mysql.connection.rollback()
                flash(f"Error al guardar el email de la empresa: {e}", "danger")

            finally:
                cur.close()

        elif formulario == "logo":
            ruta_logo = guardar_logo(request.files.get("logo"))

            try:
                if ruta_logo:
                    cur.execute("""
                        UPDATE empresas SET logo = %s WHERE id = %s
                    """, (ruta_logo, empresa_id))
                    mysql.connection.commit()
                    flash("Logo actualizado correctamente.", "success")
                else:
                    flash("Subí una imagen válida (PNG, JPG o WEBP).", "danger")

            except Exception as e:
                mysql.connection.rollback()
                flash(f"Error al guardar el logo: {e}", "danger")

            finally:
                cur.close()

        else:
            cur.close()

        return redirect(url_for("configuracion.configuracion"))

    meta_mensual_negocio = obtener_meta(cur, empresa_id, "meta_mensual_negocio")

    cur.execute("""
        SELECT email, email_password_app, logo
        FROM empresas
        WHERE id = %s
    """, (empresa_id,))
    fila_empresa = cur.fetchone()
    cur.close()

    empresa_email = fila_empresa[0] if fila_empresa else ""
    tiene_password_app = bool(fila_empresa and fila_empresa[1])
    empresa_logo = fila_empresa[2] if fila_empresa else None

    return render_template(
        "configuracion/configuracion.html",
        meta_mensual_negocio=meta_mensual_negocio,
        empresa_email=empresa_email,
        tiene_password_app=tiene_password_app,
        empresa_logo=empresa_logo
    )
