# server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, messaging, db  # <- إضافة db هنا
import os
import json
import time  # <- إضافة time هنا

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
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://naqesnarabie-default-rtdb.europe-west1.firebasedatabase.app/"
})

COOLDOWN_HOURS = 1.0  # ساعة واحدة
ROOM_PATH = "/Requests/room"

def get_player_last_accepted(player_id):
    snap = db.reference(f"Requests/acceptedHistory/{player_id}/lastAccepted").get()
    return snap or 0

def send_fcm_method(token, title, body, request_id):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=token,
            data={"reqId": request_id}
        )
        messaging.send(message)
        print(f"Sent notification for request {request_id}")
    except Exception as e:
        print(f"Error sending FCM: {e}")

def poll_requests():
    ref = db.reference(ROOM_PATH)
    while True:
        snapshot = ref.get() or {}
        for req_id, request in snapshot.items():
            city = request.get("city")
            # notified = request.get("notified") or {}

            players = db.reference("players").get() or {}
            for pid, pdata in players.items():
                # تحقق من المدينة
                if pdata.get("city") != city:
                    continue
                # تحقق من cooldown
                # last_accepted = get_player_last_accepted(pid)
                # if time.time() * 1000 - last_accepted < COOLDOWN_HOURS * 3600 * 1000:
                #     continue
                # تحقق من عدم الإشعار المكرر
                # if notified.get(pid):
                #     continue
                # إرسال الإشعار
                token = pdata.get("token")
                if token:
                    send_fcm_method(token, "طلب جديد", f"هناك طلب جديد في {city}", req_id)
                    # تحديث notified
                    db.reference(f"{ROOM_PATH}/{req_id}/notified/{pid}").set(True)
        time.sleep(5)  # التحقق كل 5 ثواني

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

@app.get("/")
def home():
    return {"status": "FCM server running"}

if __name__ == "__main__":
    poll_requests()
