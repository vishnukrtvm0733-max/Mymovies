import os
from pyrogram import Client
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
import uvicorn

API_ID = 1087031
API_HASH = "bb081cad2785a8b8cbc98cdd7be26cca"
CHANNEL_ID = -1002262225380
SESSION_FILE = "session_string.txt"

app = FastAPI()
# Temporary state for the login process
login_data = {"phone": None, "hash": None, "temp_client": None}
# The main client that will run the app
tg_client = None

async def start_telegram():
    global tg_client
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            session_string = f.read().strip()
        tg_client = Client("my_app", session_string=session_string, api_id=API_ID, api_hash=API_HASH)
        await tg_client.start()
        print("✅ Session loaded from file. App is Ready!")

@app.on_event("startup")
async def startup():
    await start_telegram()

@app.get("/", response_class=HTMLResponse)
async def home():
    if tg_client and tg_client.is_connected:
        return FileResponse("index.html")
    return """
    <body style="background:#000; color:white; font-family:sans-serif; text-align:center; padding-top:100px;">
        <h1 style="color:#e50914">CINEMA SETUP</h1>
        <p>No active session found. Please login below:</p>
        <form action="/send-code" method="post">
            <input type="text" name="phone" placeholder="+91..." style="padding:10px; border-radius:5px;">
            <button type="submit" style="padding:10px; background:#e50914; color:white; border:none;">Send OTP</button>
        </form>
    </body>
    """

@app.post("/send-code")
async def send_code(phone: str = Form(...)):
    login_data["temp_client"] = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
    await login_data["temp_client"].connect()
    code_info = await login_data["temp_client"].send_code(phone)
    login_data["phone"] = phone
    login_data["hash"] = code_info.phone_code_hash
    return HTMLResponse(f"""
    <body style="background:#000; color:white; font-family:sans-serif; text-align:center; padding-top:100px;">
        <h2>Enter Code for {phone}</h2>
        <form action="/verify" method="post">
            <input type="text" name="otp" placeholder="12345" style="padding:10px;">
            <button type="submit">Verify</button>
        </form>
    </body>
    """)

@app.post("/verify")
async def verify(otp: str = Form(...)):
    global tg_client
    # Sign in and generate the permanent string
    await login_data["temp_client"].sign_in(login_data["phone"], login_data["hash"], otp)
    string = await login_data["temp_client"].export_session_string()
    
    # Save to file
    with open(SESSION_FILE, "w") as f:
        f.write(string)
    
    # Switch to the main client
    await login_data["temp_client"].stop()
    await start_telegram()
    return HTMLResponse("<script>window.location.href='/';</script>")

@app.get("/api/movies")
async def list_movies():
    if not tg_client: return {"movies": []}
    movies = []
    async for m in tg_client.get_chat_history(CHANNEL_ID, limit=50):
        media = m.video or m.document
        if media and "video" in (media.mime_type or ""):
            movies.append({"id": m.id, "title": media.file_name or f"Video {m.id}", "size": round(media.file_size/1048576, 2)})
    return {"movies": movies}

@app.get("/stream/{msg_id}")
async def stream(msg_id: int, request: Request):
    msg = await tg_client.get_messages(CHANNEL_ID, msg_id)
    media = msg.video or msg.document
    range_header = request.headers.get("Range", "bytes=0-")
    start = int(range_header.replace("bytes=", "").split("-")[0])
    
    async def gen():
        async for chunk in tg_client.stream_media(msg, offset=start):
            yield chunk

    return StreamingResponse(gen(), status_code=206, headers={
        "Content-Range": f"bytes {start}-{media.file_size-1}/{media.file_size}",
        "Accept-Ranges": "bytes", "Content-Type": "video/mp4",
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
