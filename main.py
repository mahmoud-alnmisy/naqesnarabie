# server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, messaging
import os
import json

app = FastAPI()

# CORS لتجربة Unity WebRequest بسهولة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# تحميل مفتاح Firebase من JSON مخزن في Environment Variable
service_account_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
cred = credentials.Certificate(json.loads(service_account_json))
firebase_admin.initialize_app(cred)

@app.get("/")
def home():
    return {"status": "FCM server running"}

@app.post("/send")
async def send_notification(request: Request):
    body = await request.json()
    
    token = body.get("token")
    title = body.get("title")
    message_body = body.get("body")
    data = body.get("data", {})

    if not token or not title or not message_body:
        return {"success": False, "error": "token, title, and body are required."}

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message_body
            ),
            token=token,
            data=data
        )
        response = messaging.send(message)
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}
