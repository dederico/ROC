from flask import Flask, request
import os
import requests
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
import tempfile
from PyPDF2 import PdfReader
from langchain_community.vectorstores import FAISS
import openai
from langchain.chains.question_answering import load_qa_chain
from langchain_openai import ChatOpenAI
import psutil
import logging

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
#twilio_phone_number = "whatsapp:+19154400045" #NUMERO EN LOCAL (NGROK, ETC...)
twilio_phone_number = "whatsapp:+5218141701647"
# Configurar aplicación Flask y logging
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

pdf_exists = False
VectorStore = None

def log_memory_usage(contexto):
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logging.debug(f"{contexto} Uso de memoria: RSS={mem_info.rss}, VMS={mem_info.vms}")

@app.route("/message", methods=["POST", "GET"])
def message():
    global pdf_exists, VectorStore
    media_content_type = request.values.get('MediaContentType0')
    pdf_url = request.values.get('MediaUrl0')
    sender_phone_number = request.values.get('From', '')
    question = request.values.get('Body', '')
    response_message = ""

    logging.debug(f"Solicitud recibida: MediaContentType0={media_content_type}, MediaUrl0={pdf_url}, From={sender_phone_number}")

    if media_content_type == 'application/pdf':
        pdf_exists = True
        logging.debug("Procesando PDF...")
        log_memory_usage("Antes de procesar el PDF")
        try:
            response = requests.get(pdf_url)
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
                pdf = PdfReader(temp_file_path)
                text = ""
                for page in pdf.pages:
                    text += page.extract_text()
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    length_function=len
                )
                chunks = text_splitter.split_text(text=text)
                embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
                if not chunks:
                    response_message = "No se encontraron fragmentos de texto en el PDF."
                else:
                    VectorStore = FAISS.from_texts(chunks, embedding=embeddings)
                    response_message = "PDF recibido, ahora puedes hacer tus preguntas."
                log_memory_usage("Después de procesar el PDF y antes de crear FAISS")
        except Exception as e:
            logging.error(f"Error al procesar el PDF: {e}")
            response_message = "Error al procesar el PDF."

    elif pdf_exists:
        logging.debug(f"Pregunta recibida: {question}")
        try:
            if VectorStore is None:
                response_message = "VectorStore no está inicializado."
                logging.error(response_message)
                raise ValueError(response_message)
            docs = VectorStore.similarity_search(query=question, k=3)
            openai.api_key = OPENAI_API_KEY
            chain = load_qa_chain(
                llm=ChatOpenAI(model="gpt-3.5-turbo", temperature=0.4),
                chain_type="stuff"
            )
            answer = chain.run(input_documents=docs, question=question)
            logging.debug(f"Respuesta generada: {answer}")

            # Enviar mensaje a través de Twilio
            if not sender_phone_number.startswith('whatsapp:+'):
                response_message = "Formato de número de teléfono del remitente inválido."
                logging.error(response_message)
                return response_message, 400
            if not twilio_phone_number.startswith('whatsapp:+'):
                response_message = "Formato de número de teléfono de Twilio inválido."
                logging.error(response_message)
                return response_message, 400

            try:
                logging.debug(f"Enviando mensaje: From={twilio_phone_number}, To={sender_phone_number}, Body={answer}")
                message = twilio_client.messages.create(
                    body=answer,
                    from_=twilio_phone_number,
                    to=sender_phone_number
                )
                logging.debug(f"Mensaje enviado con éxito: SID={message.sid}")
                return str(message.sid)
            except Exception as e:
                logging.error(f"Excepción de Twilio al enviar la respuesta: {e}")
                response_message = "No se pudo enviar el mensaje."
        except Exception as e:
            logging.error(f"Error durante el procesamiento de QA: {e}")
            response_message = "Error durante el procesamiento de QA."

    else:
        response_message = "No se ha subido ningún archivo PDF. Aún puedes hacer preguntas o decir 'hola' para continuar la conversación."
        logging.debug(response_message)

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
