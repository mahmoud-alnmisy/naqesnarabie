# server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, messaging, db  # <- إضافة db هنا
import os
import json
import time  # <- إضافة time هنا
import asyncio
from contextlib import asynccontextmanager

# app = FastAPI()

# CORS لتجربة Unity WebRequest بسهولة
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# تحميل مفتاح Firebase من JSON مخزن في Environment Variable
service_account_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
cred = credentials.Certificate(json.loads(service_account_json))
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://naqesnarabie-default-rtdb.europe-west1.firebasedatabase.app/"
})

COOLDOWN_HOURS = 1.0  # ساعة واحدة
ROOM_PATH = "/Requests/room"


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
        print(f"[FCM] Sent notification for request {request_id} → token={token[:15]}")
    except Exception as e:
        print(f"[FCM ERROR] {e}")


# -------------------------------
# Polling Worker
# -------------------------------
async def poll_requests_worker():
    """Worker يقوم بمراقبة /Requests/room كل 5 ثواني ويرسل إشعارات تلقائيًا."""
    print("🔄 poll_requests_worker started...")

    while True:
        try:
            ref = db.reference(ROOM_PATH)
            snapshot = ref.get() or {}

            players_ref = db.reference("players")
            all_players = players_ref.get() or {}

            for req_id, request in snapshot.items():
                city = request.get("city")
                if not city:
                    continue

                notified = request.get("notified", {})

                # مر على كل اللاعبين
                for pid, pdata in all_players.items():
                    player_city = pdata.get("city")
                    token = pdata.get("token")

                    if not token:
                        continue

                    # تطابق المدينة
                    if player_city != city:
                        continue

                    # لا تكرر الإشعار
                    if notified.get(pid):
                        continue

                    # أرسل الإشعار
                    send_fcm_method(token, "طلب جديد", f"هناك طلب جديد في {city}", req_id)

                    # حدث notified
                    db.reference(f"{ROOM_PATH}/{req_id}/notified/{pid}").set(True)

            # انتظر 5 ثواني
            await asyncio.sleep(5)

        except Exception as e:
            print("❌ poll error:", e)
            await asyncio.sleep(5)

# -------------------------------
# Lifespan Handler
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server starting...")

    worker_task = asyncio.create_task(poll_requests_worker())

    yield  # server is running

    print("🛑 Server shutting down...")
    worker_task.cancel()
    try:
        await worker_task
    except:
        pass


# -------------------------------
# FastAPI App
# -------------------------------
app = FastAPI(lifespan=lifespan)


@app.get("/")
def home():
    return {"message": "server running, worker active"}

@app.head("/")
def head_home():
    return {}

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
