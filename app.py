from flask import Flask, request
import os
import requests
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
#from langchain_openai import OpenAIEmbeddings
import tempfile
from PyPDF2 import PdfReader
from langchain_community.vectorstores import FAISS
import openai
from langchain.chains.question_answering import load_qa_chain
from langchain_openai import ChatOpenAI


load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = TwilioClient(account_sid, auth_token)
twilio_phone_number = "whatsapp:+19154400045"
#os.getenv('TWILIO_PHONE_NUMBER')

app = Flask(__name__)

pdf_exists = False
VectorStore = None

@app.route("/message", methods=["POST", "GET"])
def message():
    global pdf_exists, VectorStore
    media_content_type = request.values.get('MediaContentType0')
    pdf_url = request.values.get('MediaUrl0')
    sender_phone_number = request.values.get('From', '')
    print(f"Received request: MediaContentType0={media_content_type}, MediaUrl0={pdf_url}, From={sender_phone_number}")

    if media_content_type == 'application/pdf':
        pdf_exists = True
        print("Processing PDF...")
        try:
            response = requests.get(pdf_url)
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
                print(f"PDF downloaded to {temp_file_path}")
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
                    print("No text chunks found in PDF.")
                    return "No text chunks found in PDF.", 500
                VectorStore = FAISS.from_texts(chunks, embedding=embeddings)
                response = "Received, You can now ask your questions"
                print("PDF processed successfully.")
        except Exception as e:
            print(f"Error processing PDF: {e}")
            return "Error processing PDF.", 500
    
    elif pdf_exists:
        question = request.values.get('Body')
        print(f"Received question: {question}")
        try:
            docs = VectorStore.similarity_search(query=question, k=3)
            openai.api_key = OPENAI_API_KEY
            chain = load_qa_chain(
                llm=ChatOpenAI(model="gpt-3.5-turbo", temperature=0.4),
                chain_type="stuff"
            )
            answer = chain.run(input_documents=docs, question=question)
            print(f"Generated answer: {answer}")

            # Verify phone numbers
            if not sender_phone_number.startswith('whatsapp:+'):
                print(f"Invalid sender phone number format: {sender_phone_number}")
                return "Invalid sender phone number format.", 400
            if not twilio_phone_number.startswith('whatsapp:+'):
                print(f"Invalid Twilio phone number format: {twilio_phone_number}")
                return "Invalid Twilio phone number format.", 400

            # Send message via Twilio
            try:
                print(f"Sending message: From={twilio_phone_number}, To={sender_phone_number}, Body={answer}")
                message = twilio_client.messages.create(
                    body=answer,
                    from_=twilio_phone_number,
                    to=sender_phone_number
                )
                print(f"Message sent successfully: SID={message.sid}")
                return str(message.sid)
            except Exception as e:
                print(f"Twilio exception while sending answer: {e}")
                return "Failed to send message.", 500
        except Exception as e:
            print(f"Error during QA processing: {e}")
            return "Error during QA processing.", 500
    else:
        response = "No PDF file uploaded."
        print(response)
    
    try:
        print(f"Sending response: From={twilio_phone_number}, To={sender_phone_number}, Body={response}")
        message = twilio_client.messages.create(
            body=response,
            from_=twilio_phone_number,
            to=sender_phone_number
        )
        print(f"Message sent successfully: SID={message.sid}")
    except Exception as e:
        print(f"Twilio exception while sending response: {e}")
        return "Failed to send message.", 500
    
    return str(message.sid)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
