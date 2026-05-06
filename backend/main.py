import os
import re
import json
import uuid
import base64
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import httpx
import anthropic
import cv2
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

STORE_PATH = Path(__file__).parent / "captions_store.json"
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://social-media-agent-phi.vercel.app",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=str(UPLOADS_DIR)), name="media")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

BRAND_CONTEXT = """
You are a social media caption writer for a healthy food brand based in Las Vegas.
The brand makes bold, flavorful meals that are nutritious and macro-friendly.
Audience: health-conscious Vegas locals, fitness community, busy professionals aged 25-45.
Tone: confident, fun, food-passionate. Not overly formal. Minimal emojis unless it fits.
Always end captions with a soft call to action toward meal prep bookings or DM inquiries.

IMPORTANT: Write captions specifically about what you see in the image — the actual dish, ingredients, colors, and presentation.
Do not default to a generic theme. Make the caption feel like it was written for that exact photo.
You must ALWAYS respond with exactly 3 captions in the required format. Never refuse or ask for clarification.
"""


# --- Store helpers ---

def load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text())
    return {"example_captions": [], "instagram_access_token": "", "instagram_user_id": ""}


def save_store(data: dict):
    STORE_PATH.write_text(json.dumps(data, indent=2))


# --- Pydantic models ---

class CaptionsPayload(BaseModel):
    captions: list[str]

class InstagramTokenPayload(BaseModel):
    access_token: str
    user_id: str

class BufferTokenPayload(BaseModel):
    access_token: str
    profile_id: str

class PostPayload(BaseModel):
    caption: str
    image_filename: str


# --- Video/image helpers ---

def extract_frames(video_path: str, num_frames: int = 3) -> list[str]:
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = [int(total_frames * i / num_frames) for i in range(num_frames)]
    frames_b64 = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            _, buffer = cv2.imencode(".jpg", frame)
            frames_b64.append(base64.b64encode(buffer).decode("utf-8"))
    cap.release()
    return frames_b64


# --- Caption generation ---

def build_style_block(example_captions: list[str]) -> str:
    if not example_captions:
        return ""
    samples = "\n".join(f'- "{c}"' for c in example_captions[:15])
    return (
        f"\n\nIMPORTANT — Voice matching: Here are real captions from this creator's Instagram profile. "
        f"Study the exact vocabulary, sentence length, punctuation style, emoji usage, and tone. "
        f"Your captions must sound like they were written by the same person:\n{samples}\n"
    )


def parse_captions(raw: str) -> list[str]:
    captions = re.findall(r"CAPTION_\d:\s*(.+?)(?=CAPTION_\d:|MUSIC_|$)", raw, re.DOTALL)
    captions = [c.strip() for c in captions if c.strip()]

    if len(captions) < 3:
        captions = re.findall(r"(?:^|\n)\s*\d[.:]\s*(.+)", raw)
        captions = [c.strip() for c in captions if c.strip()]

    if len(captions) < 3:
        lines = [l.strip() for l in raw.strip().split("\n") if l.strip()
                 and not l.strip().startswith("MUSIC")]
        captions = lines[:3]

    while len(captions) < 3:
        captions.append("Fresh, bold, and built for your goals. DM us to book your weekly meal prep.")

    return captions[:3]


def parse_music(raw: str) -> list[dict]:
    music = []
    for m in re.finditer(r"MUSIC_\d:\s*(.+?)\s*[-–]\s*(.+?)(?=MUSIC_\d:|$)", raw, re.DOTALL):
        music.append({"artist": m.group(1).strip(), "song": m.group(2).strip()})
    return music[:3]


def generate_content(image_b64_list: list[str], media_type: str = "image/jpeg") -> dict:
    store = load_store()
    style_block = build_style_block(store.get("example_captions", []))
    system = BRAND_CONTEXT + style_block

    content = []
    for img_b64 in image_b64_list:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_b64}
        })

    content.append({
        "type": "text",
        "text": (
            "Look closely at this image and write 3 Instagram captions specifically about what you see — "
            "the dish, ingredients, textures, colors, and presentation. "
            "Match the voice style of the example captions exactly if provided.\n\n"
            "Caption styles:\n"
            "1. Casual and relatable — describe the food naturally in the creator's voice\n"
            "2. Engaging — hook or question based on the specific dish\n"
            "3. Call to action — reference the dish and invite a DM or booking\n\n"
            "Then suggest 3 real songs from Instagram's music library that match the vibe, "
            "mood, and energy of this food content. Think about the aesthetic, colors, and feeling.\n\n"
            "Format your response EXACTLY as:\n"
            "CAPTION_1: [caption]\n"
            "CAPTION_2: [caption]\n"
            "CAPTION_3: [caption]\n"
            "MUSIC_1: [Artist] - [Song Title]\n"
            "MUSIC_2: [Artist] - [Song Title]\n"
            "MUSIC_3: [Artist] - [Song Title]\n\n"
            "Keep each caption under 150 characters. No hashtags in caption body. "
            "Only suggest real, well-known songs available on Instagram."
        )
    })

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=system,
        messages=[{"role": "user", "content": content}],
    )

    raw = message.content[0].text
    log.info(f"Raw Claude response:\n{raw}")

    return {
        "captions": parse_captions(raw),
        "music": parse_music(raw),
    }


# --- Routes ---

@app.post("/generate-captions")
async def generate_captions_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    is_video = suffix in [".mp4", ".mov", ".avi", ".m4v"]
    is_image = suffix in [".jpg", ".jpeg", ".png", ".webp"]

    if not is_video and not is_image:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        log.info(f"Processing file: {file.filename} ({suffix})")
        frames = extract_frames(tmp_path) if is_video else [
            base64.b64encode(open(tmp_path, "rb").read()).decode("utf-8")
        ]
        media_type = "image/jpeg" if is_video else f"image/{suffix.lstrip('.')}"
        log.info(f"Generating captions + music for {media_type}")
        result = generate_content(frames, media_type)
        log.info(f"Generated: {result}")
        return result
    except Exception as e:
        log.error(f"Caption generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


# Manually paste example captions
@app.post("/settings/captions")
async def save_example_captions(payload: CaptionsPayload):
    store = load_store()
    store["example_captions"] = payload.captions
    save_store(store)
    return {"saved": len(payload.captions)}


@app.get("/settings/captions")
async def get_example_captions():
    store = load_store()
    return {"captions": store.get("example_captions", [])}


# Save Instagram token for auto-fetch
@app.post("/settings/instagram")
async def save_instagram_token(payload: InstagramTokenPayload):
    store = load_store()
    store["instagram_access_token"] = payload.access_token
    store["instagram_user_id"] = payload.user_id
    save_store(store)
    return {"status": "saved"}


# Auto-pull captions from Instagram profile
@app.post("/settings/sync-instagram")
async def sync_instagram_captions():
    store = load_store()
    token = store.get("instagram_access_token")
    user_id = store.get("instagram_user_id")

    if not token or not user_id:
        raise HTTPException(status_code=400, detail="Instagram not connected. Add your access token first.")

    url = f"https://graph.instagram.com/{user_id}/media"
    params = {"fields": "caption", "access_token": token, "limit": 20}

    async with httpx.AsyncClient() as http:
        res = await http.get(url, params=params)

    if res.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Instagram API error: {res.text}")

    data = res.json().get("data", [])
    captions = [p["caption"] for p in data if p.get("caption")]

    store["example_captions"] = captions
    save_store(store)

    return {"synced": len(captions), "captions": captions}


# Fetch Buffer profiles using a token
@app.get("/settings/buffer/profiles")
async def get_buffer_profiles(access_token: str):
    async with httpx.AsyncClient() as http:
        res = await http.get(
            "https://api.bufferapp.com/1/profiles.json",
            params={"access_token": access_token},
        )
    if res.status_code != 200:
        raise HTTPException(status_code=502, detail="Invalid token or Buffer error")
    profiles = res.json()
    instagram = [
        {"id": p["id"], "name": p.get("formatted_username", p.get("service_username", "Instagram"))}
        for p in profiles
        if p.get("service") == "instagram"
    ]
    return {"profiles": instagram}


# Save Buffer credentials
@app.post("/settings/buffer")
async def save_buffer_token(payload: BufferTokenPayload):
    store = load_store()
    store["buffer_access_token"] = payload.access_token
    store["buffer_profile_id"] = payload.profile_id
    save_store(store)
    log.info(f"Buffer connected: profile_id={payload.profile_id}")

    # auto-sync Instagram captions to train Claude on their voice
    if payload.access_token and payload.profile_id:
        try:
            ig_captions = await _fetch_ig_captions_from_buffer(
                payload.access_token, payload.profile_id
            )
            if ig_captions:
                store["example_captions"] = ig_captions
                save_store(store)
                log.info(f"Auto-synced {len(ig_captions)} captions from Instagram profile")
        except Exception as e:
            log.warning(f"Auto-sync captions failed (non-fatal): {e}")

    return {"status": "saved"}


class BufferTokenWithUsername(BufferTokenPayload):
    username: str = ""


@app.get("/settings/buffer")
async def get_buffer_status():
    store = load_store()
    connected = bool(store.get("buffer_access_token") and store.get("buffer_profile_id"))
    return {"connected": connected, "username": store.get("buffer_username", "")}


# Upload image and save it for posting
@app.post("/upload-media")
async def upload_media(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    return {"filename": filename}


# Post to Instagram via Buffer
@app.post("/post")
async def post_to_instagram(payload: PostPayload):
    store = load_store()
    token = store.get("buffer_access_token")
    profile_id = store.get("buffer_profile_id")

    if not token or not profile_id:
        raise HTTPException(status_code=400, detail="Buffer not connected. Add your Buffer token in settings.")

    host = os.getenv("PUBLIC_URL", "http://localhost:8000")
    image_url = f"{host}/media/{payload.image_filename}"

    async with httpx.AsyncClient() as http:
        res = await http.post(
            "https://api.bufferapp.com/1/updates/create.json",
            data={
                "profile_ids[]": profile_id,
                "text": payload.caption,
                "media[photo]": image_url,
                "now": "true",
                "access_token": token,
            },
        )

    if res.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Buffer error: {res.text}")

    return {"status": "posted", "buffer_response": res.json()}


async def _fetch_ig_captions_from_buffer(token: str, profile_id: str) -> list[str]:
    """Pull recent post captions from Instagram via Buffer to train Claude's voice."""
    async with httpx.AsyncClient() as http:
        res = await http.get(
            f"https://api.bufferapp.com/1/profiles/{profile_id}/updates/sent.json",
            params={"access_token": token, "count": 20},
        )
    if res.status_code != 200:
        return []
    updates = res.json().get("updates", [])
    return [u["text"] for u in updates if u.get("text", "").strip()]


# Logs endpoint so you can see what's happening
LOG_ENTRIES: list[dict] = []

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    duration = (datetime.now(timezone.utc) - start).total_seconds()
    entry = {
        "time": start.isoformat(),
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_s": round(duration, 3),
    }
    LOG_ENTRIES.append(entry)
    if len(LOG_ENTRIES) > 200:
        LOG_ENTRIES.pop(0)
    log.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.2f}s)")
    return response


@app.get("/logs")
def get_logs():
    return {"logs": list(reversed(LOG_ENTRIES))}


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
