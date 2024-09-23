from flask import Flask, request
import os
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories.in_memory import ChatMessageHistory
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
twilio_phone_number = "whatsapp:+19154400045"
email_sender = os.getenv('EMAIL_SENDER')
email_password = os.getenv('EMAIL_PASSWORD')
smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_username = "dederico@gmail.com"
smtp_password = "cogj ymfh bytf tgga"


# Configurar aplicación Flask y logging
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Configuración de SQLite
DATABASE_URL = "sqlite:///interactions.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Definir la tabla de Interacciones
class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_phone_number = Column(String, index=True)
    question = Column(Text)
    response = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Crear la tabla en la base de datos
Base.metadata.create_all(bind=engine)

# Prompt del sistema
system_prompt = """
Tus respuestas SON DE MENOS DE 1600 CARACTERES!
Eres Sofia, un asistente virtual empático y casi humano del Gobierno Estatal de Coahuila. 
Ayudas a los vecinos a resolver sus problemas y responder sus preguntas de manera eficiente y amable. 
Tu objetivo es que los usuarios de tu servicio siempre terminen muy contentos. 
Puedes aceptar reportes, quejas, sugerencias y todo lo que normalmente se hace en el municipio.
Sé empático, conciso, directo y útil en todas tus interacciones.
Siempre presentate, y pide el nombre del cliente.
Cuando se hace un reporte entregas siempre un número de folio, solicitas solamente la información fundamental, y preguntas si el reporte es anonimo o quieren incluir su nombre.
Antes de finalizar, generas un resumen del reporte mas o menos así:
El número de folio siempre será diferente.
El Tiempo de respuesta puedes calcularlo en base a tu experiencia.
    Nombre: [Cliente que Genera Reporte]
    Folio: [REP-XXXXXXX] 
    Descripción: [Información sobre el reporte del cliente]
    Tiempo de Respuesta: [3 días]
Que te servíra para confirmar, despues de confirmar de forma positiva, agradeces por su reporte, y le comentas que darás seguimiento y compartirás actualizaciones por este medio.
Si te preguntan algo sobre la pagina, o sus tramites, buscas la informacion.
"""

# Inicializar diccionario de historiales de conversación
user_histories = {}

def split_message(message, limit=1600):
    """
    Divide el mensaje en partes de tamaño `limit`.
    """
    return [message[i:i + limit] for i in range(0, len(message), limit)]

# Función para truncar el mensaje si es necesario
def truncate_message(message, limit=1600):
    if len(message) > limit:
        logging.warning(f"Mensaje truncado a {limit} caracteres.")
        return message[:limit] + "..."  # Añade "..." para indicar que el mensaje fue truncado
    return message

# Función para scrape y limpieza de HTML
def scrape_and_clean(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Limpiar el contenido (ejemplo simple, puedes ajustarlo)
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator=" ")
    return ' '.join(text.split())

# Función para enviar correos electrónicos
def send_email(to_address, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = smtp_username
    msg['To'] = "dederico@gmail.com"

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_username, smtp_password)
            server.sendmail(email_sender, to_address, msg.as_string())
            logging.debug("Correo enviado con éxito.")
    except Exception as e:
        logging.error(f"Error al enviar el correo: {e}")

# Función para activar el segundo robot
def start_second_robot(sender_phone_number, chat_history):
    transcripcion = "La transcripción de la llamada que recibiste."
    
    try:
        action_chat = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY, temperature=0.2)
        action_prompt = """
    Eres un asistente encargado de analizar transcripciones y determinar la acción adecuada. 
    Las opciones son: 
    1. Enviar Reporte a Área Operativa:
    Ejemplo: "Hay un bache en la calle", "Las luminarias no funcionan", "Alguien tiró basura en el parque."
    2. Enviar Queja a Área de Participación Ciudadana:
    Ejemplo: "Estoy muy inconforme con el servicio", "Nadie ha atendido mi queja", "No estoy satisfecho con la respuesta que recibí."
    3. Enviar Correo a Ciudadano con la transcripción:
    Ejemplo: "¿Podrías enviarme la transcripción de esta llamada?", "Necesito un registro de esta conversación."
    4. Confirmar cita a través de correo:
    Ejemplo: "Me gustaría confirmar la cita", "¿Podrías confirmar mi cita para mañana?"
    Por favor, analiza la siguiente transcripción y determina la acción adecuada según los ejemplos anteriores.
    """

        # Imprimir chat_history para depuración
        print("Historial de chat:", chat_history)

        # Usar chat_history directamente
        action_response = action_chat.invoke([
            {"role": "system", "content": action_prompt}
        ] + [{"role": "user", "content": msg.content} for msg in chat_history])
        
        determined_action = action_response.content.strip().lower()

        if "reporte" in determined_action or "bache" in determined_action or "luminaria" in determined_action or "basura" in determined_action:
            endpoint_url = "https://administracion-estatal.coahuila.gob.mx/endpoint"
            report_data = {"transcripcion": " ".join([msg.content for msg in chat_history])}
            requests.post(endpoint_url, json=report_data)
            logging.debug("Reporte enviado a Área Operativa.")
        
        elif "queja" in determined_action or "inconforme" in determined_action:
            email_recipient = "participacion.ciudadana@coahuila.gob.mx"
            send_email(email_recipient, "Nueva Queja Recibida", " ".join([msg.content for msg in chat_history]))
            logging.debug("Queja enviada a Participación Ciudadana.")
        
        elif "correo" in determined_action or "transcripción" in determined_action:
            send_email(sender_phone_number + "@example.com", "Transcripción de la Conversación", " ".join([msg.content for msg in chat_history]))
            logging.debug("Correo enviado al ciudadano.")

        elif "cita" in determined_action and "confirmar" in determined_action:
            send_email("dederico@gmail.com", "Confirmación de Cita", " ".join([msg.content for msg in chat_history]))
            logging.debug("Correo enviado para confirmar cita.")

        else:
            logging.warning("No se pudo determinar una acción específica.")
        
    except Exception as e:
        logging.error(f"Error al analizar el historial de conversación: {e}")

@app.route("/", methods=["POST", "GET"])
def message():
    sender_phone_number = request.values.get('From', '')
    question = request.values.get('Body', '').strip().lower()
    response_message = ""

    logging.debug(f"Solicitud recibida: From={sender_phone_number}, Body={question}")

    # Obtener o crear el historial de conversación del usuario
    if sender_phone_number not in user_histories:
        user_histories[sender_phone_number] = ChatMessageHistory()
    user_history = user_histories[sender_phone_number]

    # Nueva sección: Comprobar si se envió la palabra clave para finalizar
    if question == "finalizar" or question == "terminar":
        start_second_robot(sender_phone_number, user_history.messages)
        response_message = "Sesión finalizada. La transcripción de la llamada será procesada."
        return response_message

    # Agregar el mensaje de usuario a la memoria
    user_history.add_user_message(question)

    # Crear una sesión de base de datos
    db = SessionLocal()

    try:
        # Scraping y limpieza de las páginas web
        web_info_1 = scrape_and_clean('https://coahuila.gob.mx/')
        web_info_2 = scrape_and_clean('http://www.segobcoahuila.gob.mx')

        # Inicializar el modelo OpenAI
        chat = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY, temperature=0.4)
        
        # Obtener el historial de conversación
        chat_history = user_history.messages

        # Generar la respuesta del modelo con el contexto adicional
        response = chat.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Información adicional: {web_info_1}, {web_info_2}"}
        ] + [{"role": "user", "content": msg.content} for msg in chat_history] + [{"role": "user", "content": question}])
        
        response_message = response.content

        # Truncar el mensaje si es necesario
        response_message = truncate_message(response_message)

        # Agregar la respuesta del modelo a la memoria
        user_history.add_ai_message(response_message)

        # Guardar la interacción en la base de datos
        new_interaction = Interaction(
            sender_phone_number=sender_phone_number,
            question=question,
            response=response_message
        )
        db.add(new_interaction)
        db.commit()

        logging.debug(f"Respuesta generada: {response_message}")
    except Exception as e:
        logging.error(f"Error durante la generación de respuesta: {e}")
        response_message = "Ocurrió un error al procesar tu pregunta. Por favor, intenta nuevamente."

    finally:
        db.close()

    # Enviar la respuesta al usuario
    try:
        if sender_phone_number:
            logging.debug(f"Enviando respuesta: From={twilio_phone_number}, To={sender_phone_number}, Body={response_message}")
            message = twilio_client.messages.create(
                body=response_message,
                from_=twilio_phone_number,
                to=sender_phone_number
            )
            logging.debug(f"Mensaje enviado con éxito: SID={message.sid}")
        return str(message.sid)
    except Exception as e:
        logging.error(f"Excepción de Twilio al enviar la respuesta: {e}")
        return "No se pudo enviar el mensaje.", 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5500))
    app.run(host='0.0.0.0', port=port, debug=True)