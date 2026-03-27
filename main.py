from pyrogram import Client
from fastapi import FastAPI, Request, Header
from fastapi.responses import StreamingResponse, FileResponse
import uvicorn

API_ID = 1087031
API_HASH = "bb081cad2785a8b8cbc98cdd7be26cca"
CHANNEL_ID = -1002262225380

app = FastAPI()
client = Client("user_session", api_id=API_ID, api_hash=API_HASH)

@app.on_event("startup")
async def startup():
    await client.start()

@app.get("/")
async def index():
    return FileResponse("index.html")

@app.get("/api/movies")
async def get_movies():
    movies = []
    async for m in client.get_chat_history(CHANNEL_ID, limit=50):
        media = m.video or m.document
        if media and "video" in (media.mime_type or ""):
            movies.append({
                "id": m.id, 
                "title": media.file_name or f"Video {m.id}", 
                "size": round(media.file_size / (1024*1024), 2)
            })
    return {"movies": movies}

@app.get("/stream/{msg_id}")
async def stream_video(msg_id: int, request: Request):
    msg = await client.get_messages(CHANNEL_ID, msg_id)
    media = msg.video or msg.document
    file_size = media.file_size

    # Handle Range (Crucial for skipping without buffering)
    range_header = request.headers.get("Range", "bytes=0-")
    start = int(range_header.replace("bytes=", "").split("-")[0])
    end = file_size - 1

    # Chunked generator: Reads Telegram data in small bursts
    async def chunk_generator():
        async for chunk in client.stream_media(msg, offset=start):
            yield chunk

    return StreamingResponse(
        chunk_generator(),
        status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size - start),
            "Content-Type": "video/mp4",
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
