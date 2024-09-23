from flask import Flask, request
import os
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories.in_memory import ChatMessageHistory
import logging
from cep_client import CepClient  # Asume que el cliente está en un archivo llamado cep_client.py

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
twilio_phone_number = "whatsapp:+5218141701647"

# Configurar aplicación Flask y logging
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Inicializar diccionario de historiales de conversación
user_histories = {}
user_data = {}  # Diccionario para almacenar datos temporales del usuario

# Inicializar el cliente de la API
base_url = "https://sandbox.link.kiban.com/api/v2"
api_key = os.getenv('CEP_API_KEY')
cep_client = CepClient(base_url, api_key)

@app.route("/message", methods=["POST", "GET"])
def message():
    sender_phone_number = request.values.get('From', '')
    question = request.values.get('Body', '').strip()
    response_message = ""

    logging.debug(f"Solicitud recibida: From={sender_phone_number}, Body={question}")

    # Obtener o crear el historial de conversación del usuario
    if sender_phone_number not in user_histories:
        user_histories[sender_phone_number] = ChatMessageHistory()
        user_data[sender_phone_number] = {}  # Crear un nuevo diccionario para almacenar datos

    user_history = user_histories[sender_phone_number]
    user_history.add_user_message(question)

    # Lógica de recopilación de datos
    if "tipoCriterio" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["tipoCriterio"] = question
        response_message = "Por favor, proporciona la fecha (YYYY-MM-DD):"
    elif "fecha" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["fecha"] = question
        response_message = "Por favor, proporciona el criterio:"
    elif "criterio" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["criterio"] = question
        response_message = "Por favor, proporciona el emisor:"
    elif "emisor" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["emisor"] = question
        response_message = "Por favor, proporciona el receptor:"
    elif "receptor" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["receptor"] = question
        response_message = "Por favor, proporciona la cuenta:"
    elif "cuenta" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["cuenta"] = question
        response_message = "¿El receptor es participante? (Sí/No):"
    elif "receptorParticipante" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["receptorParticipante"] = True if question.lower() == "sí" else False
        response_message = "Por favor, proporciona el monto:"
    elif "monto" not in user_data[sender_phone_number]:
        user_data[sender_phone_number]["monto"] = float(question)

        # Llamar al cliente CEPClient con los datos recopilados
        try:
            cep_response = cep_client.get_cep_pdf(
                user_data[sender_phone_number]["tipoCriterio"],
                user_data[sender_phone_number]["fecha"],
                user_data[sender_phone_number]["criterio"],
                user_data[sender_phone_number]["emisor"],
                user_data[sender_phone_number]["receptor"],
                user_data[sender_phone_number]["cuenta"],
                user_data[sender_phone_number]["receptorParticipante"],
                user_data[sender_phone_number]["monto"]
            )
            response_message = f"El PDF se ha descargado exitosamente: {cep_response}"
        except Exception as e:
            logging.error(f"Error al obtener el PDF: {e}")
            response_message = "Ocurrió un error al procesar tu solicitud. Por favor, intenta nuevamente."

        # Limpiar los datos del usuario después de la operación
        user_data.pop(sender_phone_number, None)
    else:
        # Respuesta predeterminada si hay un error en el flujo
        response_message = "No entendí tu solicitud. Por favor, proporciona la información solicitada."

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
