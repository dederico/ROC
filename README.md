## Chat With your PDF Project ##

### Environment variables
TWILIO_ACCOUNT_SID=<YOUR_TWILIO_ACCOUNT_SID>

TWILIO_AUTH_TOKEN=<YOUR_TWILIO_AUTH_TOKEN>

TWILIO_PHONE_NUMBER=<YOUR_TWILIO_PHONE_NUMBER>

OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>

### Libraries
Twilio

```pip install twilio```

Langchain

```pip install langchain```

PyPDF

```pip install PyPDF2```

Python Dotenv

```pip install python-dotenv```

OpenAI

```pip install openai```


### From the root directory

```python app.py```


### Ngrok

```ngrok http 5000```

- That's going to expose localhost:5000

**Grab the "forwarding" value: https://example1234-example.ngrok-free.app**

**And add it to your twilio configuration**




