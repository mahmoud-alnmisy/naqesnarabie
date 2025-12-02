# server.py
from fastapi import FastAPI
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, messaging, db
import json
import os
import threading
import time

app = FastAPI()

# ========================
# إعداد Firebase
# ========================
cred_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")  # يجب أن يكون JSON كامل هنا
cred = credentials.Certificate(json.loads(cred_json))
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://naqesnarabie-default-rtdb.europe-west1.firebasedatabase.app/"  # استبدل بمشروعك
})

# ========================
# نموذج بيانات الإشعار اليدوي
# ========================
class NotificationRequest(BaseModel):
    user_id: str
    title: str
    body: str
    req_id: str

# ========================
# Endpoint إرسال إشعار يدوي (اختياري)
# ========================
@app.post("/send_event_notification")
async def send_event_notification(req: NotificationRequest):
    token = db.reference(f"players/{req.user_id}/token").get()
    if not token or token == "StubToken":
        return {"success": False, "error": f"Invalid token: {token}"}

    try:
        message_id = messaging.send(messaging.Message(
            notification=messaging.Notification(title=req.title, body=req.body),
            token=token,
            data={"reqId": req.req_id}
        ))
        return {"success": True, "message_id": message_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ========================
# Polling دوري لمراقبة الطلبات
# ========================
last_checked = {}

def send_notifications(req_id, data):
    # إشعار الطلب الجديد
    owner_id = data.get("ownerId")
    city = data.get("city", "")
    if owner_id:
        token = db.reference(f"players/{owner_id}/token").get()
        if token and token != "StubToken":
            try:
                message_id = messaging.send(messaging.Message(
                    notification=messaging.Notification(
                        title="طلب جديد",
                        body=f"هناك طلب جديد في {city}"
                    ),
                    token=token,
                    data={"reqId": req_id}
                ))
                print(f"Notification sent to {owner_id}, message_id={message_id}")
            except Exception as e:
                print(f"Failed to send notification to {owner_id}: {e}")

    # إشعارات القبول/الرفض
    for child_type in ["playeraccepted", "rejects"]:
        for uid in data.get(child_type, {}):
            token = db.reference(f"players/{uid}/token").get()
            if token and token != "StubToken":
                action_text = "قام بقبول طلبك ✅" if child_type=="playeraccepted" else "قام برفض طلبك ❌"
                try:
                    message_id = messaging.send(messaging.Message(
                        notification=messaging.Notification(title="تحديث طلب", body=action_text),
                        token=token,
                        data={"reqId": req_id}
                    ))
                    print(f"Notification sent to {uid}, message_id={message_id}")
                except Exception as e:
                    print(f"Failed to send notification to {uid}: {e}")

def poll_requests():
    global last_checked
    ref = db.reference("/Requests/room")
    print("Polling Firebase for request changes...")
    while True:
        snapshot = ref.get() or {}
        for req_id, data in snapshot.items():
            # حدث جديد
            if req_id not in last_checked:
                last_checked[req_id] = data
                send_notifications(req_id, data)
            else:
                # تحقق من تحديثات القبول/الرفض
                old = last_checked[req_id]
                if old.get("playeraccepted") != data.get("playeraccepted") or \
                   old.get("rejects") != data.get("rejects"):
                    last_checked[req_id] = data
                    send_notifications(req_id, data)
        time.sleep(2)  # polling كل ثانيتين

# تشغيل Polling في Thread مستقل
threading.Thread(target=poll_requests, daemon=True).start()

# ========================
# Endpoint اختباري
# ========================
@app.get("/")
async def home():
    return {"status": "Server running. Polling Firebase for requests."}
