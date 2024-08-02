from flask import Flask, request
import os
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories.in_memory import ChatMessageHistory  # Importar la clase correcta
import logging

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
twilio_phone_number = "whatsapp:+5218141701647"
#twilio_phone_number = "whatsapp:+19154400045"

# Configurar aplicación Flask y logging
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Prompt del sistema
system_prompt = """
Eres Samantha, un asistente virtual empático y casi humano del Municipio de San Pedro Garza García. 
Ayudas a los vecinos a resolver sus problemas y responder sus preguntas de manera eficiente y amable. 
Tu objetivo es que los usuarios de tu servicio siempre terminen muy contentos. 
Puedes aceptar reportes, quejas, sugerencias y todo lo que normalmente se hace en el municipio.
Sé empático, conciso, directo y útil en todas tus interacciones.
Es muy importante, que en todos los reportes tengas la ubicación.
Siempre presentate, y pide el nombre del cliente.
Cuando se hace un reporte entregas siempre un número de folio, solicitas solamente la información fundamental, y preguntas si el reporte es anonimo o quieren incluir su nombre.
Antes de finalizar, generas un resumen del reporte mas o menos así:
El número de folio siempre será diferente.
Solicita TODA LA INFORMACION, sobre el reporte, pregunta, consulta o queja que haga el vecino, NO puedes dejar la informacion como el ejemplo que tienes a cpontinuación.
El Tiempo de respuesta puedes calcularlo en base a tu experiencia.
    Nombre: [Cliente que Genera Reporte]
    Folio: [REP-XXXXXXX] 
    Ubicacion: [Ubicación de la descripción]
    Descripción: [Información sobre el reporte del cliente]
    Tiempo de Respuesta: [3 días]
Que te servíra para confirmar, despues de confirmar de forma positiva, agradeces por su reporte, y le comentas que darás seguimiento y compartirás actualizaciones por este medio.
"""

# Inicializar ChatMessageHistory
memory = ChatMessageHistory()

@app.route("/message", methods=["POST", "GET"])
def message():
    sender_phone_number = request.values.get('From', '')
    question = request.values.get('Body', '')
    response_message = ""

    logging.debug(f"Solicitud recibida: From={sender_phone_number}, Body={question}")

    # Agregar el mensaje de usuario a la memoria
    memory.add_user_message(question)

    try:
        # Inicializar el modelo OpenAI
        chat = ChatOpenAI(model="gpt-3.5-turbo", api_key=OPENAI_API_KEY, temperature=0.4)
        
        # Obtener el historial de conversación
        chat_history = memory.messages

        # Generar la respuesta del modelo
        response = chat.invoke([
            {"role": "system", "content": system_prompt}
        ] + chat_history + [{"role": "user", "content": question}])
        
        response_message = response.content

        # Agregar la respuesta del modelo a la memoria
        memory.add_ai_message(response_message)

        logging.debug(f"Respuesta generada: {response_message}")
    except Exception as e:
        logging.error(f"Error durante la generación de respuesta: {e}")
        response_message = "Ocurrió un error al procesar tu pregunta. Por favor, intenta nuevamente."

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
