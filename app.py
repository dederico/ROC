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

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
twilio_phone_number = "whatsapp:+19154400045"

# Configure Flask app and logging
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

pdf_exists = False
VectorStore = None

def log_memory_usage(context):
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logging.debug(f"{context} Memory Usage: RSS={mem_info.rss}, VMS={mem_info.vms}")

@app.route("/message", methods=["POST", "GET"])
def message():
    global pdf_exists, VectorStore
    media_content_type = request.values.get('MediaContentType0')
    pdf_url = request.values.get('MediaUrl0')
    sender_phone_number = request.values.get('From', '')
    question = request.values.get('Body', '')
    response_message = ""

    logging.debug(f"Received request: MediaContentType0={media_content_type}, MediaUrl0={pdf_url}, From={sender_phone_number}")

    if media_content_type == 'application/pdf':
        pdf_exists = True
        logging.debug("Processing PDF...")
        log_memory_usage("Before PDF processing")
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
                    response_message = "No text chunks found in PDF."
                else:
                    VectorStore = FAISS.from_texts(chunks, embedding=embeddings)
                    response_message = "Received, You can now ask your questions"
                log_memory_usage("After PDF processing and before FAISS creation")
        except Exception as e:
            logging.error(f"Error processing PDF: {e}")
            response_message = "Error processing PDF."

    elif pdf_exists:
        logging.debug(f"Received question: {question}")
        try:
            if VectorStore is None:
                response_message = "VectorStore is not initialized."
                logging.error(response_message)
                raise ValueError(response_message)
            docs = VectorStore.similarity_search(query=question, k=3)
            openai.api_key = OPENAI_API_KEY
            chain = load_qa_chain(
                llm=ChatOpenAI(model="gpt-3.5-turbo", temperature=0.4),
                chain_type="stuff"
            )
            answer = chain.run(input_documents=docs, question=question)
            logging.debug(f"Generated answer: {answer}")

            # Send message via Twilio
            if not sender_phone_number.startswith('whatsapp:+'):
                response_message = "Invalid sender phone number format."
                logging.error(response_message)
                return response_message, 400
            if not twilio_phone_number.startswith('whatsapp:+'):
                response_message = "Invalid Twilio phone number format."
                logging.error(response_message)
                return response_message, 400

            try:
                logging.debug(f"Sending message: From={twilio_phone_number}, To={sender_phone_number}, Body={answer}")
                message = twilio_client.messages.create(
                    body=answer,
                    from_=twilio_phone_number,
                    to=sender_phone_number
                )
                logging.debug(f"Message sent successfully: SID={message.sid}")
                return str(message.sid)
            except Exception as e:
                logging.error(f"Twilio exception while sending answer: {e}")
                response_message = "Failed to send message."
        except Exception as e:
            logging.error(f"Error during QA processing: {e}")
            response_message = "Error during QA processing."

    else:
        response_message = "No PDF file uploaded. You can still ask questions or say 'hello' to continue the conversation."
        logging.debug(response_message)

    try:
        if sender_phone_number:
            logging.debug(f"Sending response: From={twilio_phone_number}, To={sender_phone_number}, Body={response_message}")
            message = twilio_client.messages.create(
                body=response_message,
                from_=twilio_phone_number,
                to=sender_phone_number
            )
            logging.debug(f"Message sent successfully: SID={message.sid}")
        return str(message.sid)
    except Exception as e:
        logging.error(f"Twilio exception while sending response: {e}")
        return "Failed to send message.", 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5500))
    app.run(host='0.0.0.0', port=port, debug=True)
