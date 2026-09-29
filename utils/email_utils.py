import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from extensions import mysql


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def obtener_credenciales_email(empresa_id):
    """
    Devuelve (email_remitente, password_app) configurados por la empresa,
    o (None, None) si todavía no cargaron su email/contraseña de aplicación
    en Configuración.
    """
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT email, email_password_app
        FROM empresas
        WHERE id = %s
    """, (empresa_id,))
    fila = cur.fetchone()
    cur.close()

    if not fila:
        return None, None

    return fila[0], fila[1]


def enviar_email(destinatario, asunto, mensaje_html, empresa_id):
    """
    Envía un email usando la casilla de correo configurada por la empresa
    (cargada en Configuración). Si la empresa todavía no configuró su email
    y contraseña de aplicación, no envía nada y devuelve False.
    """
    if not destinatario:
        return False

    remitente, password = obtener_credenciales_email(empresa_id)

    if not remitente or not password:
        print("No se pudo enviar el email: la empresa no configuró su casilla de correo en Configuración.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = remitente
        msg["To"] = destinatario
        msg["Subject"] = asunto

        msg.attach(MIMEText(mensaje_html, "html"))

        servidor = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        servidor.starttls()
        servidor.login(remitente, password)
        servidor.sendmail(remitente, destinatario, msg.as_string())
        servidor.quit()

        return True

    except Exception as e:
        print("Error al enviar email:", e)
        return False