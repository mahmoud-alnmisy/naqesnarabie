from fastapi import FastAPI
import firebase_admin
from firebase_admin import credentials, messaging
import os
import json

app = FastAPI()

# Load service account JSON from environment variable
service_account_data = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))

cred = credentials.Certificate(service_account_data)
firebase_admin.initialize_app(cred)

@app.get("/")
def home():
    return {"status": "FCM server running"}

@app.post("/send")
async def send_notification(token: str, title: str, body: str):

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=token
    )

    response = messaging.send(message)
    return {"success": True, "response": response}
