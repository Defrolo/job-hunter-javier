import datetime
import os
import sys
import json
import hashlib
import requests
from bs4 import BeautifulSoup
import re
import time

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except ImportError:
    print("Reportlab not available.")

from email_notifier import send_job_notification

# Configuration
TARGET_TIMES = [(8, 30), (12, 0), (15, 30), (18, 0)]
HISTORY_FILE = "job_history.json"
MIN_MATCH_SCORE_FOR_EMAIL = 75
MIN_MATCH_SCORE_FOR_PDF = 70
MAX_JOBS_TO_PROCESS = 20  # Limit to avoid overload

def is_it_time_to_run():
    """Check if current time matches one of our target times (Spain time)"""
    if os.environ.get("FORCE_RUN") == "true" or os.environ.get("GITHUB_ACTIONS") == "true":
        print("Ejecutando por disparador directo de GitHub Actions / Cloud.")
        return True

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Europe/Madrid")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=1))  # CET
    
    now = datetime.datetime.now(tz)
    print(f"Hora actual (España): {now.strftime('%H:%M:%S')}")
    
    if now.weekday() > 4:  # Weekend
        print("Fin de semana: búsqueda desactivada.")
        return False

    for h, m in TARGET_TIMES:
        if now.hour == h and abs(now.minute - m) <= 15:
            print(f"Horario coincidente: {h:02d}:{m:02d}. Iniciando búsqueda...")
            return True
            
    print("Fuera de ventana horaria objetivo.")
    return False

def load_job_history():
    """Load previously processed job IDs to avoid duplicates"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_job_history(job_ids):
    """Save processed job IDs to avoid duplicates"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(list(job_ids), f)

def calculate_match_score(job, cv_data):
    """
    Calculate match score between job and CV
    Returns score from 0-100
    """
    score = 0
    max_score = 100
    
    # Location match (20 points)
    job_location = job.get('location', '').lower()
    cv_location = cv_data.get('location', '').lower()
    if 'mataró' in job_location or 'barcelona' in job_location:
        score += 20
    elif 'maresme' in job_location or 'vallès' in job_location:
        score += 15
    elif 'remoto' in job_location:
        score += 10
    
    # Experience match (25 points)
    job_exp = job.get('experience_required', '').lower()
    cv_exp_years = cv_data.get('years_experience', 0)
    if 'no se requiere experiencia' in job_exp or 'junior' in job_exp or 'entry-level' in job_exp:
        score += 25  # Perfect match for entry-level
    elif '1 año' in job_exp or '6 meses' in job_exp:
        if cv_exp_years >= 0.5:
            score += 20
        else:
            score += 10
    elif '2 años' in job_exp:
        if cv_exp_years >= 2:
            score += 25
        elif cv_exp_years >= 1:
            score += 15
        else:
            score += 5
    
    # Skills match (30 points)
    job_skills = job.get('skills', '').lower()
    cv_skills = cv_data.get('skills', '').lower()
    
    # Technical skills
    tech_skills = ['soporte it', 'helpdesk', 'windows', 'linux', 'active directory', 
                   'office 365', 'outlook', 'ticketing', 'redes', 'lan', 'wan']
    tech_matches = sum(1 for skill in tech_skills if skill in job_skills and skill in cv_skills)
    score += min(tech_matches * 3, 15)  # Max 15 points for tech skills
    
    # Soft skills
    soft_skills = ['atención al cliente', 'trabajo en equipo', 'comunicación', 
                   'responsable', 'organizado', 'proactivo']
    soft_matches = sum(1 for skill in soft_skills if skill in job_skills and skill in cv_skills)
    score += min(soft_matches * 2, 15)  # Max 15 points for soft skills
    
    # Education/Training match (15 points)
    job_education = job.get('education_required', '').lower()
    cv_education = cv_data.get('education', '').lower()
    if 'no se requiere formación específica' in job_education or 'fp básica' in job_education:
        score += 15
    elif 'cfgs' in job_education or 'grado medio' in job_education:
        if 'cfgs' in cv_education or 'grado medio' in cv_education:
            score += 15
        elif 'cfpm' in cv_education or 'grado superior' in cv_education:
            score += 12
        else:
            score += 8
    
    # Language match (10 points)
    job_languages = job.get('languages', '').lower()
    cv_languages = cv_data.get('languages', '').lower()
    if 'español' in job_languages and 'castellano' in cv_languages:
        score += 5
    if 'catalán' in job_languages and ('catalán' in cv_languages or 'c1' in cv_languages):
        score += 5
    
    return min(score, max_score)

def load_cv_data():
    """Load and parse CV data for matching"""
    cv_path = "CV_Agente_Javier.txt"
    if not os.path.exists(cv_path):
        return {
            "location": "mataró, barcelona",
            "years_experience": 8,
            "skills": "soporte it, windows, linux, active directory, office 365, outlook, ticketing, redes, lan, wan, hardware, software, atención al cliente, trabajo en equipo, comunicación, responsable, organizado, proactivo, aprendizaje rápido",
            "education": "cfgs (50% completado), formación autodidacta continua",
            "languages": "castellano nativo, catalán c1, inglés a1 (en formación)"
        }
    
    try:
        with open(cv_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple parsing - in reality would be more sophisticated
        location = "mataró, barcelona"
        years_experience = 8  # From CV
        skills = "soporte it, windows, linux, active directory, office 365, outlook, ticketing, redes, lan, wan, hardware, software, atención al cliente, trabajo en equipo, comunicación, responsable, organizado, proactivo, aprendizaje rápido, sql, python, docker, ollama"
        education = "cfgs (50% completado), formación autodidacta continua en sql, python, docker, ia"
        languages = "castellano nativo, catalán c1, inglés a1 (en formación), alemán a1"
        
        return {
            "location": location,
            "years_experience": years_experience,
            "skills": skills,
            "education": education,
            "languages": languages
        }
    except Exception as e:
        print(f"Error parsing CV: {e}")
        return {
            "location": "mataró, barcelona",
            "years_experience": 8,
            "skills": "soporte it, windows, linux, active directory, office 365, outlook, ticketing, redes, lan, wan",
            "education": "cfgs (50% completado)",
            "languages": "castellano nativo, catalán c1, inglés a1"
        }

def search_infojobs():
    """Search InfoJobs for relevant positions"""
    jobs = []
    
    # InfoJobs search URLs for different categories
    search_queries = [
        "soporte it junior barcelona",
        "helpdesk barcelona",
        "técnico informático barcelona",
        "operario almacén barcelona",
        "reponedor barcelona",
        "auxiliar de tienda barcelona",
        "auxiliar de almacén barcelona",
        "auxiliar de logística barcelona"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for query in search_queries[:3]:  # Limit to avoid too many requests
        try:
            url = f"https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={query.replace(' ', '+')}&province=9&sinceDate=3"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find job cards (this is simplified - actual parsing would need adjustment)
                job_cards = soup.find_all('div', class_='job-card') or soup.find_all('article', class_='result-item')
                
                for card in job_cards[:5]:  # Limit per search
                    try:
                        title_elem = card.find('h2') or card.find('h3') or card.find('a', class_='job-title')
                        company_elem = card.find('span', class_='company') or card.find('div', class_='company')
                        location_elem = card.find('span', class_='location') or card.find('div', class_='location')
                        date_elem = card.find('span', class_='date') or card.find('div', class_='date')
                        link_elem = card.find('a', href=True)
                        
                        if title_elem and company_elem:
                            job = {
                                'title': title_elem.get_text(strip=True),
                                'company': company_elem.get_text(strip=True),
                                'location': location_elem.get_text(strip=True) if location_elem else 'Barcelona',
                                'date': date_elem.get_text(strip=True) if date_elem else 'Reciente',
                                'url': link_elem['href'] if link_elem and link_elem.has_attr('href') else '#',
                                'source': 'InfoJobs'
                            }
                            
                            # Extract basic info from text
                            full_text = card.get_text().lower()
                            job['description'] = full_text
                            
                            # Simple experience extraction
                            if 'no se requiere experiencia' in full_text or 'junior' in full_text or 'entry-level' in full_text:
                                job['experience_required'] = 'No se requiere experiencia'
                            elif '1 año' in full_text:
                                job['experience_required'] = '1 año'
                            elif '2 años' in full_text:
                                job['experience_required'] = '2 años'
                            else:
                                job['experience_required'] = 'Experiencia requerida'
                            
                            # Simple skills extraction
                            skills_list = []
                            skill_keywords = ['soporte it', 'helpdesk', 'windows', 'linux', 'office', 'excel', 
                                            'word', 'outlook', 'ticketing', 'redes', 'lan', 'wan', 'hardware', 
                                            'software', 'atención al cliente', 'trabajo en equipo']
                            for skill in skill_keywords:
                                if skill in full_text:
                                    skills_list.append(skill)
                            job['skills'] = ', '.join(skills_list) if skills_list else 'No especificado'
                            
                            # Simple education extraction
                            if 'fpi' in full_text or 'grado medio' in full_text:
                                job['education_required'] = 'Grado Medio o equivalente'
                            elif 'fps' in full_text or 'grado superior' in full_text:
                                job['education_required'] = 'Grado Superior o equivalente'
                            else:
                                job['education_required'] = 'No especificado'
                            
                            jobs.append(job)
                    except Exception as e:
                        print(f"Error parsing job card: {e}")
                        continue
            else:
                print(f"InfoJobs request failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error searching InfoJobs for '{query}': {e}")
        
        time.sleep(1)  # Be respectful to the server
    
    return jobs

def search_tecnoempleo():
    """Search Tecnoempleo for relevant positions"""
    jobs = []
    
    search_queries = [
        "soporte tecnico junior barcelona",
        "helpdesk barcelona",
        "técnico informático barcelona",
        "operario almacén barcelona"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for query in search_queries[:2]:  # Limit requests
        try:
            url = f"https://www.tecnoempleo.com/ofertas-trabajo/{query.replace(' ', '-')}.html"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find job listings
                job_elements = soup.find_all('div', class_='job-item') or soup.find_all('article', class_='oferta')
                
                for job_elem in job_elements[:3]:
                    try:
                        title_elem = job_elem.find('h2') or job_elem.find('h3')
                        company_elem = job_elem.find('span', class_='company') or job_elem.find('div', class_='empresa')
                        location_elem = job_elem.find('span', class_='location')
                        date_elem = job_elem.find('span', class_='date')
                        link_elem = job_elem.find('a', href=True)
                        
                        if title_elem and company_elem:
                            job = {
                                'title': title_elem.get_text(strip=True),
                                'company': company_elem.get_text(strip=True),
                'location': location_elem.get_text(strip=True) if location_elem else 'Barcelona',
                'date': date_elem.get_text(strip=True) if date_elem else 'Reciente',
                'url': link_elem['href'] if link_elem and link_elem.has_attr('href') else '#',
                'source': 'Tecnoempleo'
            }
                            
                            full_text = job_elem.get_text().lower()
                            job['description'] = full_text
                            
                            # Extract experience
                            if 'no se requiere experiencia' in full_text or 'junior' in full_text:
                                job['experience_required'] = 'No se requiere experiencia'
                            elif '1 año' in full_text:
                                job['experience_required'] = '1 año'
                            elif '2 años' in full_text:
                                job['experience_required'] = '2 años'
                            else:
                                job['experience_required'] = 'Experiencia requerida'
                            
                            # Extract skills
                            skills_list = []
                            skill_keywords = ['soporte it', 'helpdesk', 'windows', 'linux', 'office', 'excel', 
                                            'word', 'outlook', 'ticketing', 'redes', 'lan', 'wan', 'hardware', 
                                            'software', 'atención al cliente', 'trabajo en equipo']
                            for skill in skill_keywords:
                                if skill in full_text:
                                    skills_list.append(skill)
                            job['skills'] = ', '.join(skills_list) if skills_list else 'No especificado'
                            
                            jobs.append(job)
                    except Exception as e:
                        print(f"Error parsing Tecnoempleo job: {e}")
                        continue
            else:
                print(f"Tecnoempleo request failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error searching Tecnoempleo for '{query}': {e}")
        
        time.sleep(1)
    
    return jobs

def generate_pdf_in_cloud(title, content, filename):
    """Generate a simple PDF in the cloud environment"""
    try:
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles['Title']), Spacer(1, 12)]
        
        for line in content.split('\n'):
            if line.strip():
                story.append(Paragraph(line, styles['Normal']))
                story.append(Spacer(1, 6))
                
        doc.build(story)
        return filename
    except Exception as e:
        print(f"Error generating PDF {filename}: {e}")
        return None

def run_job_search():
    """Main job search function"""
    print("--- INICIANDO BÚSQUEDA DE EMPLEO MEJORADA ---")
    
    # Load data
    cv_data = load_cv_data()
    job_history = load_job_history()
    new_job_history = job_history.copy()
    
    print(f"CV cargado: {cv_data['years_experience']} años de experiencia")
    print(f"Historial de trabajos: {len(job_history)} trabajos procesados previamente")
    
    # Search for jobs
    print("Buscando ofertas en InfoJobs...")
    infojobs_jobs = search_infojobs()
    print(f"Encontradas {len(infojobs_jobs)} ofertas en InfoJobs")
    
    print("Buscando ofertas en Tecnoempleo...")
    tecnoempleo_jobs = search_tecnoempleo()
    print(f"Encontradas {len(tecnoempleo_jobs)} ofertas en Tecnoempleo")
    
    all_jobs = infojobs_jobs + tecnoempleo_jobs
    print(f"Total ofertas encontradas: {len(all_jobs)}")
    
    # Process jobs
    processed_count = 0
    email_sent_count = 0
    pdf_generated_count = 0
    
    for job in all_jobs[:MAX_JOBS_TO_PROCESS]:
        # Create unique ID for job
        job_id = hashlib.md5(
            f"{job.get('title', '')}{job.get('company', '')}{job.get('url', '')}".encode()
        ).hexdigest()
        
        if job_id in job_history:
            print(f"Omitiendo trabajo ya procesado: {job.get('title', 'N/A')} en {job.get('company', 'N/A')}")
            continue
        
        # Calculate match score
        match_score = calculate_match_score(job, cv_data)
        print(f"Procesando: {job.get('title', 'N/A')} en {job.get('company', 'N/A')} - Match: {match_score}%")
        
        # Process based on match score
        if match_score >= MIN_MATCH_SCORE_FOR_EMAIL:
            print(f"¡Oferta Encajada! ({match_score}%). Generando PDFs y enviando notificación...")
            
            # Generate content for PDFs
            cv_content = f"""CV Adaptado para {job.get('title', 'Puesto')}
Javier Rodríguez López
Mataró (Barcelona)
Contacto: jrlmoh@gmail.com
LinkedIn: linkedin.com/in/javier-rodríguez-lópez
GitHub: github.com/Defrolo

PERFIL PROFESIONAL
Profesional con {cv_data['years_experience']}+ años de experiencia en soporte técnico, logística y desarrollo web.
Experiencia en resolución de incidencias N1/N2, configuración de redes, gestión de sistemas.
Capacidad demostrada de aprendizaje rápido y adaptación a nuevos entornos.

COMPETENCIAS TÉCNICAS
• Sistemas: Windows 11, Linux, macOS, Active Directory, Office 365
• Redes: LAN/WLAN, TCP/IP, Firewalls
• Hardware: Montaje, diagnóstico, reparación
• Software: Herramientas de ticketing, software de soporte
• Otros: SQL básico, Python, Docker, agentes LLM

EXPERIENCIA RELEVANTE
• Soporte IT Freelance (2018-presente): Resolución de incidencias, optimización de sistemas
• Logística y Almacén: Gestión de inventarios, manejo de PDA, carretilla
• Atención al Cliente: Gestión de incidencias, comunicación efectiva

FORMACIÓN
• Grado Medio en SMR (50% completado)
• Formación autodidacta continua en tecnologías de soporte y desarrollo
"""
            
            carta_content = f"""Estimados/as,

Me dirijo a ustedes para presentar mi candidatura al puesto de {job.get('title', 'Puesto')} en {job.get('company', 'Empresa')}.

Con {cv_data['years_experience']}+ años de experiencia en soporte técnico, logística y desarrollo web, y con formación en Sistemas Microinformáticos (SMR), cuento con una base sólida para contribuir efectivamente a su equipo.

Destaco mi experiencia en:
- Resolución de incidencias técnicas N1/N2 en entornos multiplataforma
- Configuración y optimización de redes LAN/WLAN con enfoque en seguridad
- Gestión de sistemas de ticketing y atención al usuario
- Manejo de inventarios y activos tecnológicos mediante PDA y sistemas de control
- Capacidad de aprendizaje rápido demostrada en dominio autodidacta de SQL, Python, Docker y tecnologías de IA

Mi perfil combina experiencia técnica sólida con habilidades interpersonales desarrolladas en entornos de atención al cliente y trabajo en equipo, lo que me permite comunicar eficazmente soluciones técnicas a usuarios no técnicos.

Me incorporaría inmediatamente y aportaría mi experiencia técnica y mi capacidad de aprendizaje para contribuir al equipo de {job.get('company', 'Empresa')}.

Atentamente,
Javier Rodríguez López
644 17 66 02
jrlmoh@gmail.com
"""
            
            # Generate PDFs
            cv_pdf = generate_pdf_in_cloud(
                f"CV - {job.get('title', 'Puesto')}", 
                cv_content, 
                f"CV_{job.get('company', 'Empresa')}_{job.get('title', 'Puesto').replace(' ', '_')}.pdf"
            )
            
            carta_pdf = generate_pdf_in_cloud(
                f"Carta - {job.get('company', 'Empresa')}", 
                carta_content, 
                f"Carta_{job.get('company', 'Empresa')}_{job.get('title', 'Puesto').replace(' ', '_')}.pdf"
            )
            
            # Prepare email
            subject = f"🎯 [Oferta Encajada - {match_score}%] - {job.get('title', 'Puesto')} en {job.get('company', 'Empresa')}"
            
            # Build points fuertes
            points_fuertes = []
            if cv_content:
                lines = [line.strip() for line in cv_content.split('\n') if line.strip() and len(line.strip()) > 10]
                points_fuertes = lines[:5] if len(lines) >= 5 else lines
            
            points_fuertes_text = ""
            if points_fuertes:
                points_fuertes_text = chr(10).join(['• ' + point for point in points_fuertes])
            else:
                points_fuertes_text = "Experiencia técnica relevante y capacidad de aprendizaje rápido"
            
            # Build requisitos a revisar
            requisitos_text = []
            req_items = [
                f"Experiencia requerida: {job.get('experience_required', 'No especificada')}",
                f"Formación requerida: {job.get('education_required', 'No especificada')}",
                "Idiomas requeridos: No especificada" if 'idioma' not in job.get('description', '').lower() else 'Revisar requisitos de idioma',
                "Disponibilidad horaria: Verificar compatibilidad con horarios laborales"
            ]
            requisitos_text = chr(10).join(['• ' + item for item in req_items])
            
            body = f"""Puesto y Empresa: {job.get('title', 'Puesto')} en {job.get('company', 'Empresa')}
Ubicación y Modalidad: {job.get('location', 'No especificada')} ({job.get('date', 'Fecha no especificada')})
Porcentaje de encaje: {match_score}%

Puntos fuertes:
{points_fuertes_text}

Requisitos a revisar / advertencias:
{requisitos_text}

Enlace directo: {job.get('url', '#')}

*Se adjuntan los PDFs optimizados listos para enviar.*
"""
            
            # Send email
            res = send_job_notification(subject=subject, body=body, attachment_paths=[cv_pdf, carta_pdf] if cv_pdf and carta_pdf else [])
            print(f"Resultado envío email: {res}")
            
            if res.get('success'):
                email_sent_count += 1
                if cv_pdf:
                    pdf_generated_count += 1
                if carta_pdf:
                    pdf_generated_count += 1
            
            new_job_history.add(job_id)
            processed_count += 1
            
        elif match_score >= MIN_MATCH_SCORE_FOR_PDF:
            print(f"Oferta viable ({match_score}%). Generando PDFs sin notificación por email...")
            
            # Generate PDFs for review (no email)
            cv_content = f"""CV para revisión - {job.get('title', 'Puesto')}
Javier Rodríguez López
Mataró (Barcelona)
Contacto: jrlmoh@gmail.com

PERFIL PROFESIONAL
Profesional con {cv_data['years_experience']}+ años de experiencia en soporte técnico, logística y desarrollo web.
Experiencia en resolución de incidencias N1/N2, configuración de redes, gestión de sistemas.
Capacidad demostrada de aprendizaje rápido y adaptación a nuevos entornos.

COMPETENCIAS TÉCNICAS
• Sistemas: Windows 11, Linux, macOS, Active Directory, Office 365
• Redes: LAN/WLAN, TCP/IP, Firewalls
• Hardware: Montaje, diagnóstico, reparación
• Software: Herramientas de ticketing, software de soporte
• Otros: SQL básico, Python, Docker, agentes LMM

EXPERIENCIA RELEVANTE
• Soporte IT Freelance (2018-presente): Resolución de incidencias, optimización de sistemas
• Logística y Almacén: Gestión de inventarios, manejo de PDA, carretilla
• Atención al Cliente: Gestión de incidencias, comunicación efectiva

FORMACIÓN
• Grado Medio en SMR (50% completado)
• Formación autodidacta continua en tecnologías de soporte y desarrollo
"""
            
            carta_content = f"""Estimados/as,

Me dirijo a ustedes para expresar mi interés en el puesto de {job.get('title', 'Puesto')} en {job.get('company', 'Empresa')}.

Con {cv_data['years_experience']}+ años de experiencia en soporte técnico, logística y desarrollo web, creo que mi perfil podría ser de interés para su equipo.

Destaco mi experiencia en resolución de incidencias técnicas, configuración de redes, gestión de sistemas y manejo de inventarios, así como mi capacidad de aprendizaje rápido y adaptación a nuevos entornos.

Me gustaría tener la oportunidad de conversar sobre cómo mi experiencia podría contribuir a su equipo.

Atentamente,
Javier Rodríguez López
644 17 66 02
jrlmoh@gmail.com
"""
            
            # Generate PDFs
            cv_pdf = generate_pdf_in_cloud(
                f"CV - {job.get('title', 'Puesto')}_revision", 
                cv_content, 
                f"CV_REVISION_{job.get('company', 'Empresa')}_{job.get('title', 'Puesto').replace(' ', '_')}.pdf"
            )
            
            carta_pdf = generate_pdf_in_cloud(
                f"Carta - {job.get('company', 'Empresa')}_revision", 
                carta_content, 
                f"Carta_REVISION_{job.get('company', 'Empresa')}_{job.get('title', 'Puesto').replace(' ', '_')}.pdf"
            )
            
            new_job_history.add(job_id)
            processed_count += 1
            pdf_generated_count += (1 if cv_pdf else 0) + (1 if carta_pdf else 0)
            
        else:
            print(f"Oferta descartada por baja compatibilidad ({match_score}% < {MIN_MATCH_SCORE_FOR_PDF}).")
    
    # Save updated history
    save_job_history(new_job_history)
    
    print(f"""--- RESUMEN DE BÚSQUEDA ---
Ofertas procesadas: {processed_count}
Emails enviados: {email_sent_count}
PDFs generados: {pdf_generated_count}
Trabajos en historial: {len(new_job_history)}
""")
    
    return processed_count > 0

if __name__ == "__main__":
    if is_it_time_to_run():
        run_job_search()
    else:
        print("Fuera de horario permitido. Finalizando.")
        sys.exit(0)