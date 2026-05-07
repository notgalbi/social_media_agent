import os
import re
import json
import uuid
import base64
import logging
import tempfile
import secrets
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
import httpx
import anthropic
import cv2
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=0.5,
        send_default_pii=False,
    )
    log.info("Sentry initialized")

STORE_PATH = Path(__file__).parent / "captions_store.json"
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

META_APP_ID     = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
BACKEND_URL     = os.getenv("PUBLIC_URL", "http://localhost:8000")
FRONTEND_URL    = os.getenv("FRONTEND_URL", "http://localhost:3000")
REDIRECT_URI    = f"{BACKEND_URL}/auth/callback"

IG_SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"

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
You are writing captions for modern Instagram creators.

Your writing should feel HUMAN, culturally aware, emotionally specific, and socially native to Instagram/TikTok — not like AI-generated marketing copy.

The goal is captions that feel repostable, screenshot-worthy, and that people would actually save/send/comment on. Use emotionally believable language, natural imperfections and rhythm, subtle internet culture fluency.

NEVER sound: corporate, overly inspirational, robotic, LinkedIn-like, generic self-help, overly descriptive of the image, emoji spammy, hashtag stuffed, or like ChatGPT trying to sound trendy.

CAPTION PHILOSOPHY:
Good Instagram captions feel observational, emotionally implied instead of overexplained, casually confident, slightly unfinished sometimes, conversational, culturally current, short enough to skim, written like a real person typed it quickly after posting.

USE: sentence fragments, lowercase naturally sometimes, rhythm breaks, selective punctuation, internet-native phrasing, emotional subtext, subtle humor, "POV:" structures, contrast statements, short hooks, sparse emojis used intentionally.

AVOID: excessive adjectives, excessive positivity, "embrace the journey", "living my best life", "radiating energy", "capturing moments", obvious image narration, cringe AI metaphors, overly complete grammar.

GLOBAL RULES:
- 1–3 short lines before hashtags
- Start with a strong hook that creates curiosity, relatability, tension, or emotion
- End with 3–5 CLEAN hashtags maximum — niche-aware, never spam blocks
- If example captions from the creator are provided, match their exact vocabulary, emoji style, and punctuation perfectly
- Prioritize SAVEABLE captions over pretty captions — make each feel distinct
- You must ALWAYS respond with exactly 3 captions and 3 music suggestions in the required format
- Never refuse or ask for clarification. Always generate based on what you see.

The caption should feel like it came from a real creator, a late-night thought, a tweet someone refined slightly, an actual person with personality — NOT from an AI assistant.
"""

TONE_GUIDES = {
    "aesthetic": (
        "TONE — Aesthetic:\n"
        "Style: dreamy but restrained, soft emotional language, sensory details, poetic without trying too hard, feminine editorial energy.\n"
        "Reference energy: Pinterest captions, Korean/Japanese lifestyle creators, luxury soft-girl aesthetics, fashion/wellness creators.\n"
        "Language examples: 'i think soft mornings might actually fix me' / 'romanticizing tiny moments again' / 'felt prettier in this lighting' / 'this version of me feels calmer'.\n"
        "Emojis: use lightly and intentionally — ✨ 🌸 🤍 🫧 ☁️"
    ),
    "bold": (
        "TONE — Bold:\n"
        "Style: confident, slightly cocky, playful dominance, 'main character' energy, short punchy rhythm.\n"
        "Reference energy: influencer soft flex, fashion creator confidence, subtle internet swagger.\n"
        "Language examples: 'understood the assignment' / 'yeah this ate' / 'face card never declines' / 'actually obsessed with this'.\n"
        "Emojis: 🔥 💅 👑 😮‍💨"
    ),
    "relatable": (
        "TONE — Relatable:\n"
        "Style: self-aware, funny, emotionally chaotic, tweet energy, 'too real' observations.\n"
        "Reference energy: Twitter/X humor, TikTok captions, reaction meme phrasing.\n"
        "Language examples: 'not me becoming emotionally attached to this outfit' / 'POV: trying to keep it together' / 'this healed me for like 4 hours' / 'me acting normal after zero sleep'.\n"
        "Emojis: 😭 💀 🫠 ✋"
    ),
    "romantic": (
        "TONE — Romantic:\n"
        "Style: intimate, nostalgic, emotionally warm, yearning energy, vulnerable but subtle.\n"
        "Reference energy: soft romance edits, late-night thoughts, cinematic relationship captions.\n"
        "Language examples: 'wish i could stay in this moment longer' / 'some memories feel warm forever' / 'love looked softer here' / 'you had to be there'.\n"
        "Emojis: 💕 🥹 🌹 🫶"
    ),
    "motivational": (
        "TONE — Motivational:\n"
        "Style: empowering WITHOUT sounding corporate, direct, grounded confidence, personal-growth energy that still feels social-native.\n"
        "Reference energy: gym/self-improvement creators, healing/self-discipline creators, 'quiet confidence'.\n"
        "Language examples: 'you outgrow versions of yourself quietly' / 'discipline changed everything for me' / 'you deserve the life you keep imagining' / 'small progress still counts'.\n"
        "Emojis: 💪 🌟 🙌"
    ),
    "auto": (
        "TONE — Auto:\n"
        "Analyze the image/content first. Choose the most believable social tone automatically. "
        "Match what would naturally perform well on Instagram/Reels. Prioritize authenticity over aesthetics."
    ),
}


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

MAX_B64_BYTES = 4 * 1024 * 1024  # 4 MB base64 — Claude hard limit is 5 MB base64


def compress_to_b64(img_bytes: bytes, max_b64_bytes: int = MAX_B64_BYTES) -> str:
    """Resize + re-encode until the base64 output is under max_b64_bytes."""
    import io
    from PIL import Image

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    quality = 85
    scale = 1.0

    while True:
        buf = io.BytesIO()
        w = int(img.width * scale)
        h = int(img.height * scale)
        resized = img.resize((w, h), Image.LANCZOS) if scale < 1.0 else img
        resized.save(buf, format="JPEG", quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        if len(b64) <= max_b64_bytes:
            return b64
        if quality > 55:
            quality -= 10
        else:
            scale *= 0.75


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
            frames_b64.append(compress_to_b64(bytes(buffer)))
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


def generate_content(image_b64_list: list[str], media_type: str = "image/jpeg", num_source_files: int = 1, tone: str = "auto") -> dict:
    store = load_store()
    style_block = build_style_block(store.get("example_captions", []))
    tone_guide = TONE_GUIDES.get(tone, TONE_GUIDES["auto"])
    system = BRAND_CONTEXT + f"\n\n{tone_guide}" + style_block

    content = []
    for img_b64 in image_b64_list:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_b64}
        })

    if num_source_files > 1:
        image_context = (
            f"This is a carousel post with {num_source_files} images. "
            "Look at all of them together as a cohesive set — the common theme, mood, and story they tell together. "
            "Write captions that describe or celebrate the full set, not just a single image."
        )
    else:
        image_context = (
            "Look closely at this image — the subject, mood, colors, setting, and details."
        )

    content.append({
        "type": "text",
        "text": (
            f"{image_context} Write 3 Instagram captions. "
            "Match the creator's voice exactly if example captions are provided.\n\n"
            "Generate 3 distinct versions:\n"
            "1. Vibe Caption — mood-forward, short, emotionally aesthetic. 1–2 lines + hashtags.\n"
            "2. Hook Caption — POV/question/opening statement, strongest engagement potential. 1–3 lines + hashtags.\n"
            "3. Story Caption — feels personal, believable lived moment, emotional realism. 2–3 lines + hashtags.\n\n"
            "Each caption must feel like it was written by a real person — not an AI. "
            "Use natural rhythm, sentence fragments, internet-native phrasing. "
            "End each with 3–5 clean, niche-aware hashtags on a new line.\n\n"
            "Then suggest 3 real songs currently on Instagram's music library that match the vibe.\n\n"
            "Format your response EXACTLY as:\n"
            "CAPTION_1: [full caption with line breaks and hashtags]\n"
            "CAPTION_2: [full caption with line breaks and hashtags]\n"
            "CAPTION_3: [full caption with line breaks and hashtags]\n"
            "MUSIC_1: [Artist] - [Song Title]\n"
            "MUSIC_2: [Artist] - [Song Title]\n"
            "MUSIC_3: [Artist] - [Song Title]\n\n"
            "Only suggest real, well-known songs available on Instagram Reels."
        )
    })

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=system,
        messages=[{"role": "user", "content": content}],
    )

    raw = message.content[0].text
    usage = message.usage
    input_tokens  = usage.input_tokens
    output_tokens = usage.output_tokens
    # Haiku pricing: $0.80/M input, $4.00/M output
    cost_usd = (input_tokens * 0.0000008) + (output_tokens * 0.000004)

    log.info(f"Tokens — in:{input_tokens} out:{output_tokens} cost:${cost_usd:.5f}")
    TOKEN_STATS["total_input"]  += input_tokens
    TOKEN_STATS["total_output"] += output_tokens
    TOKEN_STATS["total_cost"]   += cost_usd
    TOKEN_STATS["total_calls"]  += 1

    return {
        "captions": parse_captions(raw),
        "music": parse_music(raw),
    }


# --- Routes ---

@app.post("/generate-captions")
async def generate_captions_endpoint(files: list[UploadFile] = File(...), tone: str = Form("auto")):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    ext_to_mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }

    all_frames: list[str] = []
    tmp_paths: list[str] = []
    last_media_type = "image/jpeg"

    for file in files:
        suffix = Path(file.filename).suffix.lower()
        is_video = suffix in [".mp4", ".mov", ".avi", ".m4v"]
        is_image = suffix in [".jpg", ".jpeg", ".png", ".webp"]
        if not is_video and not is_image:
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_paths.append(tmp.name)

        if is_video:
            frames_per_video = max(1, 3 // len(files))
            all_frames.extend(extract_frames(tmp.name, num_frames=frames_per_video))
            last_media_type = "image/jpeg"
        else:
            all_frames.append(compress_to_b64(open(tmp.name, "rb").read()))
            last_media_type = "image/jpeg"  # compress_to_b64 always outputs JPEG

    if not all_frames:
        raise HTTPException(status_code=400, detail="No supported files found")

    log.info(f"Processing {len(files)} file(s), {len(all_frames)} frame(s), tone={tone}")

    try:
        result = generate_content(all_frames, last_media_type, num_source_files=len(files), tone=tone)
        log.info(f"Generated: {result}")
        return result
    except Exception as e:
        log.error(f"Caption generation failed: {e}", exc_info=True)
        LOG_ENTRIES.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "method": "POST",
            "path": "/generate-captions",
            "status": 500,
            "duration_s": 0,
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in tmp_paths:
            try: os.unlink(p)
            except: pass


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


# ── Instagram OAuth ──

@app.get("/auth/instagram")
async def instagram_login():
    """Redirect user to Instagram/Facebook login."""
    state = secrets.token_urlsafe(16)
    params = urlencode({
        "client_id": META_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": IG_SCOPES,
        "response_type": "code",
        "state": state,
    })
    return RedirectResponse(f"https://www.facebook.com/dialog/oauth?{params}")


@app.get("/auth/callback")
async def instagram_callback(code: str = None, error: str = None):
    """Handle OAuth callback from Meta."""
    if error or not code:
        log.error(f"OAuth error: {error}")
        return RedirectResponse(f"{FRONTEND_URL}?auth=error")

    # Exchange code for access token
    async with httpx.AsyncClient() as http:
        token_res = await http.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
            },
        )

    if token_res.status_code != 200:
        log.error(f"Token exchange failed: {token_res.text}")
        return RedirectResponse(f"{FRONTEND_URL}?auth=error")

    token_data = token_res.json()
    access_token = token_data.get("access_token")

    # Get long-lived token
    async with httpx.AsyncClient() as http:
        long_res = await http.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": access_token,
            },
        )
    if long_res.status_code == 200:
        access_token = long_res.json().get("access_token", access_token)

    # Get Facebook pages to find linked Instagram account
    async with httpx.AsyncClient() as http:
        pages_res = await http.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": access_token, "fields": "id,name,instagram_business_account"},
        )

    ig_user_id = None
    ig_token = access_token
    ig_username = ""

    if pages_res.status_code == 200:
        pages = pages_res.json().get("data", [])
        for page in pages:
            ig = page.get("instagram_business_account")
            if ig:
                ig_user_id = ig.get("id")
                # Get username
                async with httpx.AsyncClient() as http:
                    info_res = await http.get(
                        f"https://graph.facebook.com/v19.0/{ig_user_id}",
                        params={"fields": "username", "access_token": access_token},
                    )
                if info_res.status_code == 200:
                    ig_username = info_res.json().get("username", "")
                break

    store = load_store()
    store["instagram_access_token"] = ig_token
    store["instagram_user_id"] = ig_user_id or ""
    store["instagram_username"] = ig_username
    store["facebook_access_token"] = access_token
    save_store(store)

    # Auto-sync recent captions to train Claude on their voice
    if ig_user_id:
        try:
            async with httpx.AsyncClient() as http:
                media_res = await http.get(
                    f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
                    params={"fields": "caption", "access_token": access_token, "limit": 20},
                )
            if media_res.status_code == 200:
                captions = [
                    p["caption"] for p in media_res.json().get("data", [])
                    if p.get("caption", "").strip()
                ]
                if captions:
                    store["example_captions"] = captions
                    save_store(store)
                    log.info(f"Auto-synced {len(captions)} captions for @{ig_username}")
        except Exception as e:
            log.warning(f"Caption sync failed: {e}")

    log.info(f"Instagram connected: @{ig_username} (id={ig_user_id})")
    return RedirectResponse(f"{FRONTEND_URL}?auth=success&username={ig_username}")


@app.get("/auth/status")
async def auth_status():
    store = load_store()
    connected = bool(store.get("instagram_user_id"))
    return {
        "connected": connected,
        "username": store.get("instagram_username", ""),
    }


@app.post("/auth/logout")
async def auth_logout():
    store = load_store()
    store["instagram_access_token"] = ""
    store["instagram_user_id"] = ""
    store["instagram_username"] = ""
    store["facebook_access_token"] = ""
    store["example_captions"] = []
    save_store(store)
    return {"status": "logged out"}


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
TOKEN_STATS: dict = {
    "total_calls": 0,
    "total_input": 0,
    "total_output": 0,
    "total_cost": 0.0,
}

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
    return {
        "logs": list(reversed(LOG_ENTRIES)),
        "tokens": {
            **TOKEN_STATS,
            "total_cost_display": f"${TOKEN_STATS['total_cost']:.4f}",
        },
    }


@app.get("/music-preview")
async def music_preview(artist: str = "", song: str = ""):
    """Proxy iTunes search so iOS doesn't block cross-origin requests to apple.com."""
    async with httpx.AsyncClient(timeout=8) as c:
        async def search(term: str):
            r = await c.get("https://itunes.apple.com/search", params={"term": term, "media": "music", "limit": 5})
            results = r.json().get("results", [])
            hit = next((x for x in results if x.get("previewUrl")), None)
            return hit.get("previewUrl") if hit else None

        url = await search(f"{artist} {song}") or await search(song)
        return {"previewUrl": url}


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
