import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def send_job_notification(
    subject: str,
    body: str,
    to_email: str = "jrlmoh@gmail.com",
    attachment_paths: list = None
) -> dict:
    """
    Envía una notificación de oferta de empleo por email vía SMTP de Gmail.
    Lee las credenciales de variables de entorno de Render.
    """
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    sender_email = os.environ.get("JOB_ALERT_EMAIL_USER", "jrlmoh@gmail.com")
    app_password = os.environ.get("JOB_ALERT_EMAIL_PASS", "").strip()

    if not app_password:
        return {
            "success": False,
            "error": "No se encontró la contraseña de aplicación de Gmail (JOB_ALERT_EMAIL_PASS)."
        }

    try:
        msg = MIMEMultipart()
        msg["From"] = f"Agente Empleabilidad IA <{sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_paths:
            for file_path in attachment_paths:
                if file_path and os.path.exists(file_path):
                    part = MIMEBase("application", "octet-stream")
                    with open(file_path, "rb") as f:
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(file_path)
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)

        return {"success": True, "message": f"Email enviado correctamente a {to_email}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
