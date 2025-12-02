from fastapi import FastAPI
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, messaging, db
import threading
import json
import os

app = FastAPI()

# إعداد Firebase
cred_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
cred = credentials.Certificate(json.loads(cred_json))
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://naqesnarabie-default-rtdb.europe-west1.firebasedatabase.app/"
})

# نموذج بيانات الإشعار
class NotificationRequest(BaseModel):
    user_id: str
    title: str
    body: str
    req_id: str

# Endpoint اختياري لإرسال إشعار يدوي
@app.post("/send_event_notification")
async def send_event_notification(req: NotificationRequest):
    token = db.reference(f"players/{req.user_id}/token").get()
    if not token:
        return {"success": False, "error": "Token not found"}

    message = messaging.Message(
        notification=messaging.Notification(title=req.title, body=req.body),
        token=token,
        data={"reqId": req.req_id}
    )
    message_id = messaging.send(message)
    return {"success": True, "message_id": message_id}

# مراقبة الطلبات الجديدة أو التغييرات
def monitor_requests():
    ref = db.reference("/Requests/room")

    def listener(event):
        snapshot = event.data
        if not snapshot:
            return

        request_id = event.path.strip("/")
        owner_id = snapshot.get("ownerId")
        city = snapshot.get("city", "")

        # إرسال إشعار للاعب إذا المدينة مطابقة
        if owner_id and city:
            token = db.reference(f"players/{owner_id}/token").get()
            if token:
                messaging.send(messaging.Message(
                    notification=messaging.Notification(
                        title="طلب جديد",
                        body=f"هناك طلب جديد في {city}"
                    ),
                    token=token,
                    data={"reqId": request_id}
                ))

        # إرسال إشعارات لكل من قبل/رفض
        for child_type in ["playeraccepted", "rejects"]:
            children = snapshot.get(child_type, {})
            for uid in children:
                token = db.reference(f"players/{uid}/token").get()
                if token:
                    action_text = "قام بقبول طلبك ✅" if child_type == "playeraccepted" else "قام برفض طلبك ❌"
                    messaging.send(messaging.Message(
                        notification=messaging.Notification(
                            title="تحديث طلب",
                            body=action_text
                        ),
                        token=token,
                        data={"reqId": request_id}
                    ))

    ref.listen(listener)

# تشغيل المراقب في Thread مستقل
threading.Thread(target=monitor_requests, daemon=True).start()
