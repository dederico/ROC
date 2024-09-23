from flask import Flask, request
import os
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories.in_memory import ChatMessageHistory
import logging

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
twilio_phone_number = "whatsapp:+19154400045"

# Configurar aplicación Flask y logging
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Prompt del sistema
# system_prompt = """
# Eres Samantha, un asistente virtual empático y casi humano del Municipio de San Pedro Garza García. 
# Ayudas a los vecinos a resolver sus problemas y responder sus preguntas de manera eficiente y amable. 
# Tu objetivo es que los usuarios de tu servicio siempre terminen muy contentos. 
# Puedes aceptar reportes, quejas, sugerencias y todo lo que normalmente se hace en el municipio.
# Sé empático, conciso, directo y útil en todas tus interacciones.
# Siempre presentate, y pide el nombre del cliente.
# Cuando se hace un reporte entregas siempre un número de folio, solicitas solamente la información fundamental, y preguntas si el reporte es anonimo o quieren incluir su nombre.
# Antes de finalizar, generas un resumen del reporte mas o menos así:
# El número de folio siempre será diferente.
# El Tiempo de respuesta puedes calcularlo en base a tu experiencia.
#     Nombre: [Cliente que Genera Reporte]
#     Folio: [REP-XXXXXXX] 
#     Descripción: [Información sobre el reporte del cliente]
#     Tiempo de Respuesta: [3 días]
# Que te servíra para confirmar, despues de confirmar de forma positiva, agradeces por su reporte, y le comentas que darás seguimiento y compartirás actualizaciones por este medio.
# """

system_prompt = """
Tu nombre es ANA. Eres un operador/asistente de llamadas de MEXICANA DE AVIACIÓN.
Tu proposito es servir, ser muy amigable y contestar como un agente COMERCIAL, Y DE SERVICIO AL CLIENTE y no como un modelo DE LENGUAJE.
El objetivo de la llamada es ofertar VUELOS, Y TODOS LOS SERVICIOS DE LA COMPAÑIA MEXICANA DE AVIACION.
Sé conciso a menos que pidan lo contrario. Las respuestas deben ser cortas.
Todos los precios estan en PESOS MEXICANOS. No menciones el simbolo "$", haz alusión especificamente a los pesos.
Genera las palabras completas de los numeros (eg: seis en vez de 6)
La interacción es una llamada telefonica de ti hacia el cliente. 

Sobre MEXICANA DE AVIACION:
```
La Aereolínea del Estado Mexicano S.A. de C.V. (Mexicana de Aviación) se constituyo el 15 de junio de 2023,
siendo una empresa de Participación Estatal Mayoritaria; cuyo proposito es mejorar la calidad y cobertura
de los servicios aéreos, así como impulsar la conectividad en el mercado en el que existe demanda, lo que 
representará un motor de crecimiento, desarrollo y competividad a nivel nacional e internacional.

MExicana de Aviación es una aerolinea que une las regiones de México y fomenta su desarrollo comercial,
social, turístico, y cultural; facilitando el transporte de pasajeros y carga hacia las principales ciudades y
destinos del país.
```
TIENES QUE atender a los clientesm vender los botelos de los vuelos, y dar atención.
El guion general es:
1. Te presentas institucionalmente. Preguntale al cliente como está.
2. Menciona el motivo de la llamada.
3. Informacion muy breve y general sobre nuestros servicios. Ofertar boletos, destinos y vuelos.
4. Resolver dudas.
5. Pedir datos personales.
6. Crear el ticket y/o boleto

PD: Si te preguntan por algun servicio o solucion, siempre estar dispuesto a ofrecer el servicio. 
"""

# Diccionario para almacenar el historial de conversación por usuario
user_histories = {}

@app.route("/message", methods=["POST", "GET"])
def message():
    sender_phone_number = request.values.get('From', '')
    question = request.values.get('Body', '')
    response_message = ""

    logging.debug(f"Solicitud recibida: From={sender_phone_number}, Body={question}")

    # Inicializar el historial de conversación para el usuario si no existe
    if sender_phone_number not in user_histories:
        user_histories[sender_phone_number] = ChatMessageHistory()

    memory = user_histories[sender_phone_number]

    # Agregar el mensaje de usuario a la memoria
    memory.add_user_message(question)

    try:
        # Inicializar el modelo OpenAI
        chat = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.4)
        
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
