from fastapi import FastAPI
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, messaging
import os
import json

app = FastAPI()

# Load service account JSON from environment variable
service_account_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not service_account_json:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable not set.")

service_account_data = json.loads(service_account_json)

cred = credentials.Certificate(service_account_data)
firebase_admin.initialize_app(cred)

@app.get("/")
def home():
    return {"status": "FCM server running"}

# Pydantic model for JSON body
class Notification(BaseModel):
    token: str
    title: str
    body: str

@app.post("/send")
async def send_notification(notification: Notification):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body
            ),
            token=notification.token
        )

        response = messaging.send(message)
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}
