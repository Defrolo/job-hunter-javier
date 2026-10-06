import datetime
import os
import sys
import time
import requests
# Nota: Reportlab se usa para generar PDFs en Render
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except ImportError:
    print("Reportlab no instalado localmente, pero se instalará en Render.")

from email_notifier import send_job_notification

# --- CONFIGURACIÓN DE HORARIOS (BARCELONA) ---
TARGET_TIMES = [(8, 30), (12, 0), (15, 30), (18, 0)]

def is_it_time_to_run():
    # Render usa UTC por defecto. Convertimos a hora de España.
    # Usamos un offset manual simple o datetime con zoneinfo si está disponible.
    # Para mayor robustez en Render (Python 3.9+), usamos zoneinfo.
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Europe/Madrid")
    except ImportError:
        # Fallback simple (UTC+2 en verano, UTC+1 en invierno) - Aproximación
        tz = datetime.timezone(datetime.timedelta(hours=2)) 
    
    now = datetime.datetime.now(tz)
    print(f"Hora actual en Barcelona: {now.strftime('%H:%M:%S')}")
    
    # Solo de Lunes a Viernes (0=Lunes, 4=Viernes)
    if now.weekday() > 4:
        print("Es fin de semana. No se realiza búsqueda.")
        return False

    for h, m in TARGET_TIMES:
        # Ventana de 10 minutos por si el cron de Render se retrasa un poco
        if now.hour == h and abs(now.minute - m) <= 10:
            print(f"Match detectado para el horario {h:02d}:{m:02d}. Iniciando búsqueda...")
            return True
            
    print("No es uno de los horarios programados. Saliendo.")
    return False

def generate_pdf_in_cloud(title, content, filename):
    """Genera un PDF simple en el entorno efímero de Render"""
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
    print("--- INICIANDO MOTOR DE BÚSQUEDA CLOUD ---")
    
    # 1. Cargar Perfil/CV (debe estar en el repo)
    cv_path = "CV_Agente_Javier.txt"
    if not os.path.exists(cv_path):
        print(f"Error: No se encuentra {cv_path}")
        return

    # 2. BÚSQUEDA SIMULADA (Para este script autónomo en Render)
    # En un entorno real en la nube sin Hermes API, usaríamos APIs de búsqueda
    # o scraping ligero. Aquí implementamos la lógica de filtrado.
    
    print("Buscando ofertas recientes en portales...")
    # Simulamos detección de una oferta para demostrar el flujo
    # En producción, aquí iría el código de requests a Infojobs/Indeed
    
    ofertas_encontradas = [
        {
            "puesto": "Técnico Soporte N1 (Ejemplo Cloud)",
            "empresa": "CloudTech Barcelona",
            "ubicacion": "Barcelona",
            "modalidad": "Híbrido",
            "match": 82,
            "puntos_fuertes": "Encaje perfecto en hardware y Windows 11. Residencia cercana.",
            "gaps": "Nivel de inglés A1 requiere defensa.",
            "url": "https://ejemplo.com/oferta-soporte"
        }
    ]

    for oferta in ofertas_encontradas:
        if oferta["match"] >= 75:
            print(f"¡Oferta Encajada! ({oferta['match']}%). Preparando notificación...")
            
            # Generar PDFs en la nube para adjuntar
            cv_pdf = generate_pdf_in_cloud(f"CV - {oferta['puesto']}", "Contenido optimizado del CV...", "CV_Optimizado.pdf")
            carta_pdf = generate_pdf_in_cloud(f"Carta - {oferta['empresa']}", "Contenido de la carta...", "Carta_Presentacion.pdf")
            
            subject = f"🎯 [Oferta Encajada - {oferta['match']}%] - {oferta['puesto']} en {oferta['empresa']}"
            body = f"""Puesto y Empresa: {oferta['puesto']} en {oferta['empresa']}
Ubicación y Modalidad: {oferta['ubicacion']} ({oferta['modalidad']})
Porcentaje de encaje: {oferta['match']}%

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

if __name__ == "__main__":
    if is_it_time_to_run():
        run_job_hunter()
    else:
        # En Render, si el script termina rápido no consume casi tiempo de cómputo
        sys.exit(0)
