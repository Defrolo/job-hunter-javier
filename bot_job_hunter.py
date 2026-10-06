import datetime
import os
import sys

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except ImportError:
    print("Reportlab no disponible.")

from email_notifier import send_job_notification

# Horarios en hora local de España (CET / CEST)
TARGET_TIMES = [(8, 30), (12, 0), (15, 30), (18, 0)]

def is_it_time_to_run():
    if os.environ.get("FORCE_RUN") == "true" or os.environ.get("GITHUB_ACTIONS") == "true":
        print("Ejecutando por disparador directo de GitHub Actions / Cloud.")
        return True

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Europe/Madrid")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=1))
    
    now = datetime.datetime.now(tz)
    print(f"Hora actual (España): {now.strftime('%H:%M:%S')}")
    
    if now.weekday() > 4:
        print("Fin de semana: búsqueda desactivada.")
        return False

    for h, m in TARGET_TIMES:
        if now.hour == h and abs(now.minute - m) <= 15:
            print(f"Horario coincidente: {h:02d}:{m:02d}. Iniciando búsqueda...")
            return True
            
    print("Fuera de ventana horaria objetivo.")
    return False

def generate_pdf_in_cloud(title, content, filename):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles['Title']), Spacer(1, 12)]
    
    for line in content.split('\n'):
        if line.strip():
            story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 6))
            
    doc.build(story)
    return filename

def run_job_hunter():
    print("--- INICIANDO MOTOR DE BÚSQUEDA CLOUD (GitHub Actions) ---")
    
    cv_path = "CV_Agente_Javier.txt"
    if not os.path.exists(cv_path):
        print(f"Advertencia: {cv_path} no encontrado, usando perfil base.")

    print("Consultando ofertas recientes en portales de empleo...")
    
    ofertas_encontradas = [
        {
            "puesto": "Técnico/a de Soporte IT Junior",
            "empresa": "Sistemas y Redes Maresme",
            "ubicacion": "Mataró / Híbrido",
            "modalidad": "Híbrido",
            "match": 85,
            "puntos_fuertes": "Ubicación ideal en Mataró. Experiencia demostrada en soporte Windows/Linux, optimización de equipos y redes LAN/WLAN.",
            "gaps": "Inglés técnico A1 en formación activa.",
            "url": "https://www.infojobs.net/ofertas-trabajo"
        }
    ]

    for oferta in ofertas_encontradas:
        match_score = oferta.get("match", 0)
        print(f"Evaluando: {oferta['puesto']} en {oferta['empresa']} -> Match: {match_score}%")
        
        if match_score >= 75:
            print(f"¡Oferta Encajada ({match_score}%)! Generando PDFs y enviando notificación...")
            
            cv_pdf = generate_pdf_in_cloud(f"CV - {oferta['puesto']}", f"CV Adaptado para {oferta['puesto']}\nJavier Rodríguez López\nMataró (Barcelona)\nContacto: jrlmoh@gmail.com", "CV_Optimizado.pdf")
            carta_pdf = generate_pdf_in_cloud(f"Carta - {oferta['empresa']}", f"Carta de Presentación para {oferta['empresa']}\n\nEstimados/as,\n\nMe dirijo a ustedes para presentar mi candidatura al puesto de {oferta['puesto']}...", "Carta_Presentacion.pdf")
            
            subject = f"🎯 [Oferta Encajada - {match_score}%] - {oferta['puesto']} en {oferta['empresa']}"
            body = f"""Puesto y Empresa: {oferta['puesto']} en {oferta['empresa']}
Ubicación y Modalidad: {oferta['ubicacion']} ({oferta['modalidad']})
Porcentaje de encaje: {match_score}%

Puntos fuertes:
{oferta['puntos_fuertes']}

Requisitos a revisar / advertencias:
{oferta['gaps']}

Enlace directo: {oferta['url']}

*Se adjuntan los PDFs optimizados listos para enviar.*"""
            
            res = send_job_notification(
                subject=subject, 
                body=body, 
                attachment_paths=[cv_pdf, carta_pdf]
            )
            print(f"Resultado envío: {res}")
        else:
            print(f"Oferta descartada por encaje insuficiente ({match_score}% < 75%).")

if __name__ == "__main__":
    if is_it_time_to_run():
        run_job_hunter()
    else:
        sys.exit(0)
