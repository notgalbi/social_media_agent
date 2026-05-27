import os
import json
import uuid
import base64
import logging
import tempfile
import secrets
import io
import time
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
import httpx
import google.generativeai as genai
from PIL import Image
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("uvicorn.error")

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=0.5,
        send_default_pii=False,
    )
    log.debug("Sentry initialized")

STORE_PATH = Path(__file__).parent / "captions_store.json"
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

ANALYTICS_DB = Path(__file__).parent / "analytics.db"
ANALYTICS_KEY = os.getenv("ANALYTICS_KEY", "captionly-admin")


def _aconn():
    conn = sqlite3.connect(str(ANALYTICS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _init_analytics():
    with _aconn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session   TEXT NOT NULL,
            event     TEXT NOT NULL,
            props     TEXT DEFAULT '{}',
            ts        TEXT NOT NULL,
            ua        TEXT DEFAULT '',
            ip        TEXT DEFAULT ''
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ev  ON events(event)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ts  ON events(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sid ON events(session)")


_init_analytics()

META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
BACKEND_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
REDIRECT_URI = f"{BACKEND_URL}/auth/callback"

IG_SCOPES = (
    "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"
)

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

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
- Start with a strong hook that creates curiosity, relatability, tension, or emotion
- Follow the HASHTAGS instruction exactly — use precisely the count specified, no more, no less
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
        "Gen Z language patterns: 'in my soft era' / 'romanticizing my life again' / 'it's giving cottagecore' / 'delulu but make it soft' / 'this is so that girl'\n"
        "Reference energy: Pinterest captions, Korean/Japanese lifestyle creators, that girl aesthetic, soft-life TikTok.\n"
        "Language examples: 'i think soft mornings might actually fix me' / 'romanticizing tiny moments again' / 'felt prettier in this lighting' / 'this version of me feels calmer' / 'in my healing era and it shows'.\n"
        "Emojis: use lightly and intentionally — ✨ 🌸 🤍 🫧 ☁️"
    ),
    "bold": (
        "TONE — Bold:\n"
        "Style: confident, slightly cocky, playful dominance, main character energy, short punchy rhythm.\n"
        "Gen Z language patterns: 'understood the assignment' / 'ate and left no crumbs' / 'face card never declines' / 'it's giving' / 'slay' / 'no notes' / 'rent free' / 'caught in 4K serving'\n"
        "Reference energy: influencer soft flex, fashion creator confidence, rizz energy, subtle internet swagger.\n"
        "Language examples: 'understood the assignment and submitted early' / 'face card expired? never heard of her' / 'yeah this ate. no crumbs.' / 'the confidence was unmatched' / 'it's giving everything it's supposed to give'.\n"
        "Emojis: 🔥 💅 👑 😮‍💨"
    ),
    "relatable": (
        "TONE — Relatable:\n"
        "Style: self-aware, funny, emotionally chaotic, tweet energy, too real observations, ironic sincerity.\n"
        "Gen Z language patterns: 'not me...' / 'POV:' / 'caught in 4K' / 'no because why' / 'i'm in my flop era' / 'the delusion is real' / 'this is so core' / 'lowkey / highkey' / 'slay i guess'\n"
        "Reference energy: FinTok chaos, relatable TikTok, therapy speak ironically, unwell behavior.\n"
        "Language examples: 'not me becoming emotionally attached to this' / 'POV: you're down bad' / 'this healed me for like 4 hours' / 'no because why does this go so hard' / 'the audacity. the nerve. the gall.' / 'i'm in my villain era apparently'.\n"
        "Emojis: 😭 💀 🫠 ✋"
    ),
    "romantic": (
        "TONE — Romantic:\n"
        "Style: intimate, nostalgic, emotionally warm, yearning energy, vulnerable but subtle. Ironic sincerity welcome.\n"
        "Gen Z language patterns: 'down bad' / 'in my lover era' / 'the way i...' / 'rent free' / 'soft launching' / 'this person lives in my head'\n"
        "Reference energy: soft romance edits, late-night thoughts, sapphic aesthetic, cinematic relationship captions.\n"
        "Language examples: 'wish i could stay in this moment longer' / 'some memories feel warm forever' / 'love looked softer here' / 'you had to be there' / 'the way this lives rent free' / 'down bad and at peace with it'.\n"
        "Emojis: 💕 🥹 🌹 🫶"
    ),
    "motivational": (
        "TONE — Motivational:\n"
        "Style: empowering WITHOUT sounding corporate or LinkedIn. Grounded, direct, feels earned not performed.\n"
        "Gen Z language patterns: 'we're not the same' / 'that girl era' / 'main character behavior' / 'doing it for the plot' / 'the glow up is real' / 'leveling up quietly'\n"
        "Reference energy: gym TikTok, that girl routines, self-discipline creators, quiet confidence aesthetic.\n"
        "Language examples: 'you outgrow versions of yourself quietly' / 'discipline changed everything for me' / 'the glow up was an inside job' / 'doing it for the plot at this point' / 'we're not the same and that's the point' / 'leveled up and didn't announce it'.\n"
        "Emojis: 💪 🌟 🙌"
    ),
    "wanderlust": (
        "TONE — Wanderlust:\n"
        "Style: adventurous, free-spirited, slightly poetic. Travel diary energy, not tourism ad energy.\n"
        "Gen Z language patterns: 'it's giving abroad era' / 'doing it for the plot' / 'main character travel' / 'no thoughts just [location]' / 'this ate differently in [city]'\n"
        "Reference energy: solo travel TikTok, van life creators, backpacking vlogs, travel that girl.\n"
        "Language examples: 'still thinking about this view' / 'some places just stay with you' / 'packed a bag and figured the rest out later' / 'new city, same chaos' / 'no thoughts just this sunset' / 'doing it for the plot and the passport stamps'.\n"
        "Emojis: 🌍 ✈️ 🗺️ 🌅"
    ),
    "funny": (
        "TONE — Funny:\n"
        "Style: pure comedy, meme-brained, absurdist, chaotic-good energy. Delivery matters — punchy last line.\n"
        "Gen Z language patterns: 'i am so normal about this' / 'we move' / 'it's giving unwell' / 'the way i...' / 'criminally [adjective]' / 'this slaps actually' / 'no thoughts head empty'\n"
        "Reference energy: Twitter/X brain rot, TikTok chaos energy, meme format captions, self-aware cringe.\n"
        "Language examples: 'this photo is doing a lot of heavy lifting' / 'criminally unhinged behavior and i stand by it' / 'i am so normal about all of this' / 'no thoughts. head empty. just vibes.' / 'the delusion that carried me here'.\n"
        "Emojis: 😂 💀 🫠 (punchline placement only)"
    ),
    "earthy": (
        "TONE — Earthy:\n"
        "Style: grounded, slow, sensory, nature-connected. Journal entry written outside, not wellness brand copy.\n"
        "Gen Z language patterns: 'in my cottage era' / 'this reset me actually' / 'slow living agenda' / 'feral but in a healing way' / 'it's giving forest'\n"
        "Reference energy: cottagecore TikTok, sustainability creators, slow living, foraging, outdoor wellness.\n"
        "Language examples: 'this is the reset i didn't know i needed' / 'good things grow slowly and so do i' / 'back to basics back to myself' / 'the earth actually fixes you' / 'in my feral forest era' / 'it's giving slow morning and i need more of this'.\n"
        "Emojis: 🌿 🍃 🌱 ☁️ (light and intentional)"
    ),
    "hustle": (
        "TONE — Hustle:\n"
        "Style: driven, direct, no-fluff. Feels earned not performed. Quiet confidence over loud grind.\n"
        "Gen Z language patterns: 'we're not the same' / 'the bag secured itself' / 'main character behavior' / 'doing it for the plot' / 'no cap' / 'different breed'\n"
        "Reference energy: entrepreneur TikTok, gym discipline creators, self-made energy, business that girl.\n"
        "Language examples: 'the work is the way' / 'nobody claps at the beginning. that's fine.' / 'building something real, no cap' / 'quiet work loud results we're not the same' / 'the bag secured itself actually' / 'different breed behavior'.\n"
        "Emojis: 💼 🔑 📈 💪 (punctuate, don't decorate)"
    ),
    "moody": (
        "TONE — Moody:\n"
        "Style: dark, cinematic, introspective, minimal. Maximum atmosphere per word. Brooding but not dramatic.\n"
        "Gen Z language patterns: 'it's giving dark academia' / 'in my villain era' / 'the vibe is unmatched' / 'lowkey unwell about this' / 'no thoughts just the aesthetic'\n"
        "Reference energy: dark academia, film photography TikTok, alt/indie creators, editorial fashion.\n"
        "Language examples: 'some feelings don't have names' / 'existing dramatically as always' / 'the light did something and i let it' / 'in my villain era and the aesthetic is immaculate' / 'lowkey unwell about this photo honestly'.\n"
        "Emojis: 🌙 🖤 🫥 (rare — punctuation only)"
    ),
    "foodie": (
        "TONE — Foodie:\n"
        "Style: sensory, indulgent, specific. Make the reader taste it. Avoid generic food praise entirely.\n"
        "Gen Z language patterns: 'this ate' / 'criminally good' / 'no crumbs left' / 'it's giving michelin' / 'the way this slaps' / 'ate this in silence out of respect'\n"
        "Reference energy: FoodTok, restaurant reviewers, home cook creators, culinary content.\n"
        "Language examples: 'criminally good. no notes.' / 'this changed my life a little bit' / 'ate this in complete silence out of respect' / 'it's giving michelin star and i'm not okay' / 'the way this slapped differently today' / 'no crumbs were left. none.'.\n"
        "Emojis: 🍽️ 🧄 🫶 ✨ (flavor only)"
    ),
    "cinematic": (
        "TONE — Cinematic:\n"
        "Style: dramatic, filmic, visual storytelling. Like a movie still caption. Short, atmospheric, directorial gaze.\n"
        "Gen Z language patterns: 'this is a film' / 'it's giving movie scene' / 'cinematic universe' / 'the director's cut'\n"
        "Reference energy: film photography, short film captions, editorial fashion, dark academia cinema.\n"
        "Language examples: 'the scene writes itself' / 'this needed a soundtrack' / 'directed by the universe' / 'cut to this' / 'the b-roll that saved the film'.\n"
        "Emojis: 🎬 🎞️ 🖤 (rare, deliberate)"
    ),
    "luxury": (
        "TONE — Luxury:\n"
        "Style: quiet luxury, elevated, aspirational but not flashy. Old money energy. Less is more.\n"
        "Gen Z language patterns: 'quiet luxury era' / 'old money aesthetic' / 'the standards are high' / 'understated everything'\n"
        "Reference energy: quiet luxury TikTok, old money aesthetic, European editorial, Loro Piana energy.\n"
        "Language examples: 'the details are everything' / 'effortless and intentional' / 'this is the standard' / 'money doesn't talk here' / 'quiet luxury is the only luxury'.\n"
        "Emojis: minimal or none — at most 🤍 🫧"
    ),
    "soft": (
        "TONE — Soft:\n"
        "Style: gentle, nurturing, tender. Soft-girl energy. Safe, warm, comforting captions.\n"
        "Gen Z language patterns: 'soft life era' / 'gentle with myself' / 'cozy season' / 'healing quietly' / 'being kind to myself'\n"
        "Reference energy: soft-girl TikTok, slow mornings, comfort content, gentle living creators.\n"
        "Language examples: 'choosing peace today' / 'soft mornings heal me' / 'being gentle with it all' / 'rest is productive too' / 'tender days like this'.\n"
        "Emojis: 🌸 🤍 🫶 ☁️"
    ),
    "chaotic": (
        "TONE — Chaotic:\n"
        "Style: unhinged, chaotic good, gremlin energy. Unpredictable, fast, funny-dark.\n"
        "Gen Z language patterns: 'no thoughts head empty' / 'i am so normal about this' / 'the chaos was planned' / 'villain arc activated'\n"
        "Reference energy: Twitter brain rot, chaotic TikTok, goblin mode, unwell-but-make-it-art.\n"
        "Language examples: 'the chaos was planned. kind of.' / 'fully unhinged and at peace with it' / 'no thoughts just vibes and poor decisions' / 'the villain origin story continues' / 'we do not explain ourselves here'.\n"
        "Emojis: 😭 💀 🫠 🔥"
    ),
    "mysterious": (
        "TONE — Mysterious:\n"
        "Style: cryptic, intriguing, dark allure. Makes people stop and re-read. Withholds more than it reveals.\n"
        "Gen Z language patterns: 'something shifted' / 'you wouldn't understand' / 'the lore deepens' / 'not everything needs to be explained'\n"
        "Reference energy: dark academia mystery, tarot aesthetic, alt-indie creators, cryptic fashion editorial.\n"
        "Language examples: 'something shifted and i can feel it' / 'not everything is meant to be explained' / 'the lore is expanding' / 'i know things' / 'we don't talk about it'.\n"
        "Emojis: 🌙 🖤 🫥 (sparse, atmospheric)"
    ),
    "auto": (
        "TONE — Auto:\n"
        "Analyze the image/content first. Choose the most believable social tone automatically. "
        "Match what would naturally perform well on Instagram/Reels. Use Gen Z-native language where it fits organically. Prioritize authenticity over aesthetics."
    ),
}


def get_length_guide(level: int) -> str:
    guides = {
        1: "LENGTH (CRITICAL): Every caption = as short as 3 words up to 1 short line before hashtags. One tight, punchy thought. If it's longer, cut it.",
        2: "LENGTH (CRITICAL): Every caption = 1–2 lines of text before hashtags. Short and deliberate. Cut any word that doesn't earn its place.",
        3: "LENGTH (CRITICAL): Every caption = 3–4 lines of text before hashtags. Hook + one real thought.",
        4: "LENGTH (CRITICAL): Every caption = 5–6 lines of text before hashtags. Room for emotion, context, and depth.",
        5: "LENGTH (CRITICAL): Every caption = 7–10 lines of text before hashtags. Full narrative — vulnerability, story, real lived moment. No filler.",
    }
    return guides.get(level, guides[2])


def get_hashtag_guide(count: int) -> str:
    if count == 0:
        return "HASHTAGS (CRITICAL): Do NOT include any hashtags whatsoever in any caption. Zero hashtags. End every caption without them."
    return f"HASHTAGS (CRITICAL): End every caption with EXACTLY {count} relevant, niche-aware hashtag{'s' if count > 1 else ''} on a new line. Not {count - 1}, not {count + 1} — exactly {count}."


def get_tone_guide(tones_str: str) -> str:
    parts = [t.strip().lower() for t in tones_str.split(",") if t.strip()]
    valid = [t for t in parts if t in TONE_GUIDES and t != "auto"]
    if not valid:
        return TONE_GUIDES["auto"]
    if len(valid) == 1:
        return TONE_GUIDES[valid[0]]
    blended = "\n\n".join(TONE_GUIDES[t] for t in valid)
    return "TONE BLEND — Combine these styles naturally. Don't alternate — merge them:\n\n" + blended


def get_genre_guide(genres_str: str, music_vibe: str = "") -> str:
    parts = [g.strip().lower() for g in genres_str.split(",") if g.strip()]
    genres = [g for g in parts if g != "auto"]
    vibe_part = f" The music should also feel like: '{music_vibe}'." if music_vibe else ""
    if not genres:
        return f"MUSIC GENRE: Choose genre matching caption energy.{vibe_part}"
    if len(genres) == 1:
        label = GENRE_LABELS.get(genres[0], genres[0])
        return f"MUSIC GENRE: All 9 songs must be {label} genre.{vibe_part}"
    labels = [GENRE_LABELS.get(g, g) for g in genres]
    labels_str = " / ".join(labels)
    return f"MUSIC GENRE: Mix these genres across the 9 suggestions: {labels_str}.{vibe_part}"


def get_emoji_guide(style: str, intensity: int) -> str:
    intensity_map = {
        0: "EMOJIS: Use zero emojis in any caption.",
        1: "EMOJIS: Use 0–1 emoji per caption — only if essential.",
        2: "EMOJIS: Use 1–3 emojis per caption, placed intentionally.",
        3: "EMOJIS: Use 3–6 emojis per caption with energy.",
    }
    base = intensity_map.get(intensity, intensity_map[2])
    if style:
        base = base + f" Preferred emoji style: {style}"
    return base


def get_custom_phrase_guide(phrases: str) -> str:
    if not phrases or not phrases.strip():
        return ""
    return f"\n\nCUSTOM PHRASES (weave in naturally where they fit): {phrases}"


# --- Store helpers ---


def load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text())
    return {
        "example_captions": [],
        "instagram_access_token": "",
        "instagram_user_id": "",
    }


def save_store(data: dict):
    STORE_PATH.write_text(json.dumps(data, indent=2))


# --- Pydantic models ---


class SongSuggestion(BaseModel):
    artist: str
    song: str


class CaptionOutput(BaseModel):
    caption_1: str
    caption_2: str
    caption_3: str
    music_1: list[SongSuggestion]
    music_2: list[SongSuggestion]
    music_3: list[SongSuggestion]


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


class AnalyticsEvent(BaseModel):
    session: str
    event: str
    props: dict = {}


# --- Analytics routes ---


@app.post("/analytics/event")
async def analytics_track(payload: AnalyticsEvent, request: Request):
    ua = request.headers.get("user-agent", "")[:200]
    raw_ip = request.client.host if request.client else ""
    ip = hashlib.sha256(raw_ip.encode()).hexdigest()[:12]
    ts = datetime.now(timezone.utc).isoformat()
    with _aconn() as c:
        c.execute(
            "INSERT INTO events (session,event,props,ts,ua,ip) VALUES (?,?,?,?,?,?)",
            (payload.session, payload.event, json.dumps(payload.props), ts, ua, ip),
        )
    return {"ok": True}


@app.get("/analytics/data")
def analytics_data(key: str = ""):
    if key != ANALYTICS_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    with _aconn() as c:
        def q(sql, *args):
            return c.execute(sql, args).fetchall()

        # Overview
        sessions_today = q("SELECT COUNT(DISTINCT session) n FROM events WHERE ts>=date('now')")
        sessions_7d    = q("SELECT COUNT(DISTINCT session) n FROM events WHERE ts>=date('now','-7 days')")
        sessions_30d   = q("SELECT COUNT(DISTINCT session) n FROM events WHERE ts>=date('now','-30 days')")
        errors_7d      = q("SELECT COUNT(*) n FROM events WHERE event='generate_error'  AND ts>=date('now','-7 days')")
        generates_7d   = q("SELECT COUNT(*) n FROM events WHERE event='generate_success' AND ts>=date('now','-7 days')")

        # Funnel (last 30d unique sessions per step)
        funnel_steps = ["app_open","file_upload","generate_success","caption_select","post_open"]
        funnel = {}
        for step in funnel_steps:
            row = c.execute("SELECT COUNT(DISTINCT session) n FROM events WHERE event=? AND ts>=date('now','-30 days')", (step,)).fetchone()
            funnel[step] = row["n"]

        # Events per day last 14d
        by_day = q("""SELECT substr(ts,1,10) day, COUNT(*) n FROM events
                      WHERE ts>=date('now','-14 days') GROUP BY day ORDER BY day""")

        # Top tones (last 30d)
        tones = q("""SELECT json_extract(props,'$.tone') tone, COUNT(*) n FROM events
                     WHERE event='tone_select' AND tone IS NOT NULL AND ts>=date('now','-30 days')
                     GROUP BY tone ORDER BY n DESC LIMIT 10""")

        # Top genres (last 30d)
        genres = q("""SELECT json_extract(props,'$.genre') genre, COUNT(*) n FROM events
                      WHERE event='genre_select' AND genre IS NOT NULL AND ts>=date('now','-30 days')
                      GROUP BY genre ORDER BY n DESC LIMIT 10""")

        # Top length levels
        lengths = q("""SELECT json_extract(props,'$.level') level, COUNT(*) n FROM events
                       WHERE event='generate_success' AND level IS NOT NULL AND ts>=date('now','-30 days')
                       GROUP BY level ORDER BY n DESC""")

        # Recent 60 events
        recent = q("SELECT session,event,props,ts FROM events ORDER BY id DESC LIMIT 60")

        # Screen views (last 30d unique sessions per screen)
        sv_raw = q("""SELECT json_extract(props,'$.screen') s, COUNT(DISTINCT session) n
                      FROM events WHERE event='screen_view' AND ts>=date('now','-30 days')
                      GROUP BY s""")
        screen_views = {r["s"]: r["n"] for r in sv_raw if r["s"]}

        # Tab switch counts (last 30d unique sessions)
        tab_raw = q("""SELECT json_extract(props,'$.tab') t, COUNT(DISTINCT session) n
                       FROM events WHERE event='tab_switch' AND ts>=date('now','-30 days')
                       GROUP BY t""")
        tab_counts = {r["t"]: r["n"] for r in tab_raw if r["t"]}

        # Screen transitions: next screen after each screen_view (last 30d)
        trans_raw = q("""
            WITH sv AS (
                SELECT session, id, json_extract(props,'$.screen') s
                FROM events WHERE event='screen_view' AND ts>=date('now','-30 days')
            )
            SELECT s1.s as from_s,
                (SELECT s2.s FROM sv s2
                 WHERE s2.session=s1.session AND s2.id>s1.id
                 ORDER BY s2.id LIMIT 1) as to_s,
                COUNT(*) n
            FROM sv s1
            GROUP BY from_s, to_s HAVING to_s IS NOT NULL
            ORDER BY n DESC LIMIT 50
        """)
        transitions = [{"from": r["from_s"], "to": r["to_s"], "n": r["n"]} for r in trans_raw]

        # Draft saves (last 30d unique sessions)
        draft_saves = q("SELECT COUNT(DISTINCT session) n FROM events WHERE event='draft_save' AND ts>=date('now','-30 days')")

        # Tab entry points — where were users when they tapped each tab (last 30d)
        tab_entries_raw = q("""
            SELECT json_extract(props,'$.tab') tab,
                   json_extract(props,'$.from') from_screen,
                   COUNT(*) n
            FROM events
            WHERE event='tab_switch'
              AND json_extract(props,'$.from') IS NOT NULL
              AND ts >= date('now','-30 days')
            GROUP BY tab, from_screen
            ORDER BY tab, n DESC
        """)
        tab_entries = {}
        for r in tab_entries_raw:
            if r["tab"] not in tab_entries:
                tab_entries[r["tab"]] = {}
            tab_entries[r["tab"]][r["from_screen"] or "unknown"] = r["n"]

    return {
        "overview": {
            "sessions_today": sessions_today[0]["n"],
            "sessions_7d":    sessions_7d[0]["n"],
            "sessions_30d":   sessions_30d[0]["n"],
            "errors_7d":      errors_7d[0]["n"],
            "generates_7d":   generates_7d[0]["n"],
        },
        "funnel":            funnel,
        "by_day":            [{"day": r["day"], "count": r["n"]} for r in by_day],
        "top_tones":         {r["tone"]: r["n"] for r in tones},
        "top_genres":        {r["genre"]: r["n"] for r in genres},
        "top_lengths":       {r["level"]: r["n"] for r in lengths},
        "screen_views":      screen_views,
        "tab_counts":        tab_counts,
        "screen_transitions":transitions,
        "draft_save_count":  draft_saves[0]["n"],
        "tab_entries":       tab_entries,
        "recent":            [{"session": r["session"][:8], "event": r["event"],
                               "props": r["props"], "ts": r["ts"][:19]} for r in recent],
    }


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Captionly — Analytics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0d0f;color:#e8e8ea;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;min-height:100vh}
header{padding:24px 32px;border-bottom:1px solid #1e1e24;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:20px;font-weight:700;letter-spacing:-0.3px;color:#fff}
header h1 span{color:#b8405a}
.badge{font-size:11px;color:#666;background:#18181d;border:1px solid #2a2a32;border-radius:6px;padding:4px 10px}
main{padding:28px 32px;display:flex;flex-direction:column;gap:28px;max-width:1400px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px}
.card{background:#13131a;border:1px solid #1e1e28;border-radius:12px;padding:18px 20px;display:flex;flex-direction:column;gap:6px}
.card-label{font-size:11px;color:#555;text-transform:uppercase;letter-spacing:1px;font-weight:600}
.card-value{font-size:32px;font-weight:700;color:#fff;line-height:1}
.card-sub{font-size:11px;color:#444}
.card.accent{border-color:#3a1520;background:#1a0e12}
.card.accent .card-value{color:#b8405a}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
@media(max-width:900px){.row2,.row3{grid-template-columns:1fr}}
.panel{background:#13131a;border:1px solid #1e1e28;border-radius:12px;padding:20px 22px;display:flex;flex-direction:column;gap:16px}
.panel-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#555}
.bar-row{display:flex;align-items:center;gap:10px;font-size:13px}
.bar-label{width:110px;flex-shrink:0;color:#aaa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-track{flex:1;background:#1e1e28;border-radius:4px;height:8px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#b8405a,#852d42);transition:width 0.6s ease}
.bar-count{width:36px;text-align:right;color:#555;flex-shrink:0;font-size:12px}
.funnel-step{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #1a1a22}
.funnel-step:last-child{border-bottom:none}
.funnel-label{width:150px;flex-shrink:0;color:#bbb;font-size:13px}
.funnel-bar{flex:1;background:#1e1e28;border-radius:4px;height:10px;overflow:hidden}
.funnel-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#b8405a 0%,#d4607c 100%)}
.funnel-n{width:60px;text-align:right;font-weight:700;color:#fff;flex-shrink:0}
.funnel-pct{width:48px;text-align:right;font-size:11px;color:#555;flex-shrink:0}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:#444;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;padding:8px 12px;border-bottom:1px solid #1e1e28}
td{padding:8px 12px;border-bottom:1px solid #161620;color:#bbb;font-family:monospace}
td.event-name{color:#e8e8ea;font-weight:600;font-family:sans-serif;font-size:13px}
td.ts{color:#444}
.tag{display:inline-block;background:#1a0e12;border:1px solid #3a1520;color:#b8405a;font-size:10px;font-weight:700;border-radius:4px;padding:2px 6px;font-family:monospace}
.loading{color:#333;font-size:16px;text-align:center;padding:80px}
canvas{width:100%!important}
.flow-wrap{overflow-x:auto;padding:4px 0 4px}
.flow-legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:8px}
.flow-legend-item{display:flex;align-items:center;gap:7px;font-size:11px;color:#555}
.flow-legend-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}
.entry-box{background:#13131a;border:1px solid #1e1e28;border-radius:12px;overflow:hidden}
.entry-box-head{padding:18px 20px 14px;border-bottom:1px solid #1a1a24;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.entry-box-icon{font-size:22px;line-height:1;flex-shrink:0;margin-top:2px}
.entry-box-meta{flex:1}
.entry-box-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#555;margin-bottom:6px}
.entry-box-total{font-size:36px;font-weight:800;color:#fff;line-height:1}
.entry-box-sub{font-size:11px;color:#444;margin-top:4px}
.entry-box-body{padding:14px 20px 18px;display:flex;flex-direction:column;gap:10px}
.entry-row{display:flex;align-items:center;gap:10px}
.entry-label{font-size:12px;color:#aaa;width:130px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.entry-track{flex:1;background:#1e1e28;border-radius:4px;height:7px;overflow:hidden}
.entry-fill{height:100%;border-radius:4px}
.entry-count{font-size:12px;color:#555;width:30px;text-align:right;flex-shrink:0}
.entry-empty{font-size:12px;color:#2a2a36;padding:16px 0;text-align:center}
</style>
</head>
<body>
<header>
  <h1>Captionly <span>Analytics</span></h1>
  <span class="badge" id="updated">Loading...</span>
</header>
<main>
  <div class="cards" id="cards"><div class="loading">Loading data...</div></div>
  <div class="row2">
    <div class="panel"><div class="panel-title">Customer Funnel — Last 30 Days</div><div id="funnel"></div></div>
    <div class="panel"><div class="panel-title">Events Per Day</div><canvas id="chart-days" height="180"></canvas></div>
  </div>
  <div class="panel">
    <div class="panel-title">Page Flow — Last 30 Days</div>
    <div class="flow-wrap" id="flow-panel"><div class="loading" style="font-size:13px;padding:40px">Loading flow data...</div></div>
    <div class="flow-legend">
      <div class="flow-legend-item"><div class="flow-legend-dot" style="background:#b8405a"></div>Main path</div>
      <div class="flow-legend-item"><div class="flow-legend-dot" style="background:#3d3d58"></div>Side path (Drafts / Settings)</div>
      <div class="flow-legend-item"><div class="flow-legend-dot" style="background:#1e1e2a"></div>No data yet</div>
    </div>
  </div>
  <div class="row3">
    <div class="entry-box">
      <div class="entry-box-head">
        <div class="entry-box-icon">⚙</div>
        <div class="entry-box-meta">
          <div class="entry-box-title">Settings · from Upload</div>
          <div class="entry-box-total" id="settings-upload-total">—</div>
          <div class="entry-box-sub">sessions tapped Settings<br>while on Upload screen</div>
        </div>
      </div>
    </div>
    <div class="entry-box">
      <div class="entry-box-head">
        <div class="entry-box-icon">⚙</div>
        <div class="entry-box-meta">
          <div class="entry-box-title">Settings · from Captions</div>
          <div class="entry-box-total" id="settings-captions-total">—</div>
          <div class="entry-box-sub">sessions tapped Settings<br>after captions generated</div>
        </div>
      </div>
    </div>
    <div class="entry-box">
      <div class="entry-box-head">
        <div class="entry-box-icon">📅</div>
        <div class="entry-box-meta">
          <div class="entry-box-title">Drafts Tab</div>
          <div class="entry-box-total" id="drafts-total">—</div>
          <div class="entry-box-sub">sessions opened Drafts</div>
        </div>
      </div>
      <div class="entry-box-body" id="drafts-entries"></div>
    </div>
  </div>
  <div class="row3">
    <div class="panel"><div class="panel-title">Top Vibes</div><div id="tones"></div></div>
    <div class="panel"><div class="panel-title">Top Genres</div><div id="genres"></div></div>
    <div class="panel"><div class="panel-title">Caption Length</div><div id="lengths"></div></div>
  </div>
  <div class="panel"><div class="panel-title">Recent Events</div><div id="recent"></div></div>
</main>
<script>
const KEY = new URLSearchParams(location.search).get("key") || "";
const API = location.origin;
const LENGTH_LABELS = {"1":"Micro","2":"Short","3":"Medium","4":"Long","5":"Story"};
const FUNNEL_LABELS = {
  app_open:"App Open",file_upload:"File Uploaded",
  generate_success:"Captions Generated",caption_select:"Caption Selected",post_open:"Post Opened"
};
let dayChart = null;

async function load() {
  const r = await fetch(`${API}/analytics/data?key=${KEY}`);
  if (!r.ok) { document.querySelector("main").innerHTML='<div class="loading">Access denied — check your key</div>'; return; }
  const d = await r.json();
  document.getElementById("updated").textContent = "Updated " + new Date().toLocaleTimeString();

  // Cards
  const ov = d.overview;
  const cvt = ov.generates_7d ? Math.round(d.funnel.post_open/(d.funnel.app_open||1)*100) : 0;
  document.getElementById("cards").innerHTML = `
    <div class="card"><div class="card-label">Sessions Today</div><div class="card-value">${ov.sessions_today}</div></div>
    <div class="card"><div class="card-label">Sessions 7d</div><div class="card-value">${ov.sessions_7d}</div></div>
    <div class="card"><div class="card-label">Sessions 30d</div><div class="card-value">${ov.sessions_30d}</div></div>
    <div class="card"><div class="card-label">Captions Gen 7d</div><div class="card-value">${ov.generates_7d}</div></div>
    <div class="card accent"><div class="card-label">End-to-End CVR</div><div class="card-value">${cvt}%</div><div class="card-sub">open → post</div></div>
    <div class="card accent"><div class="card-label">Errors 7d</div><div class="card-value">${ov.errors_7d}</div></div>
  `;

  // Funnel
  const funnelSteps = ["app_open","file_upload","generate_success","caption_select","post_open"];
  const top = d.funnel.app_open || 1;
  document.getElementById("funnel").innerHTML = funnelSteps.map(k => {
    const n = d.funnel[k] || 0;
    const pct = Math.round(n/top*100);
    return `<div class="funnel-step">
      <div class="funnel-label">${FUNNEL_LABELS[k]}</div>
      <div class="funnel-bar"><div class="funnel-fill" style="width:${pct}%"></div></div>
      <div class="funnel-n">${n}</div>
      <div class="funnel-pct">${pct}%</div>
    </div>`;
  }).join("");

  // Days chart
  const days = d.by_day;
  if (dayChart) dayChart.destroy();
  dayChart = new Chart(document.getElementById("chart-days"), {
    type:"line",
    data:{
      labels: days.map(x=>x.day.slice(5)),
      datasets:[{
        data: days.map(x=>x.count),
        fill:true,
        borderColor:"#b8405a",
        backgroundColor:"rgba(184,64,90,0.12)",
        tension:0.4,pointRadius:3,pointBackgroundColor:"#b8405a",
      }]
    },
    options:{
      plugins:{legend:{display:false}},
      scales:{
        x:{grid:{color:"#1e1e28"},ticks:{color:"#444",font:{size:11}}},
        y:{grid:{color:"#1e1e28"},ticks:{color:"#444",font:{size:11}},beginAtZero:true}
      }
    }
  });

  // Bars helper
  function bars(el, data, labelFn) {
    const max = Math.max(1,...Object.values(data));
    const html = Object.entries(data).map(([k,v]) =>
      `<div class="bar-row">
        <div class="bar-label">${labelFn ? labelFn(k) : k}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round(v/max*100)}%"></div></div>
        <div class="bar-count">${v}</div>
      </div>`
    ).join("");
    document.getElementById(el).innerHTML = html || '<div style="color:#333;padding:12px 0">No data yet</div>';
  }

  bars("tones",  d.top_tones,  null);
  bars("genres", d.top_genres, null);
  bars("lengths",d.top_lengths,k=>LENGTH_LABELS[k]||k);

  renderFlow(d);
  const st = d.tab_entries?.settings || {};
  const settUpload   = st["screen-upload"]   || 0;
  const settCaptions = st["screen-captions"] || 0;
  const settUpEl = document.getElementById("settings-upload-total");
  const settCapEl = document.getElementById("settings-captions-total");
  if (settUpEl)  settUpEl.textContent  = settUpload;
  if (settCapEl) settCapEl.textContent = settCaptions;
  renderEntries("drafts-entries", d.tab_entries?.drafts);

  // Recent events
  const rows = d.recent.map(r => {
    let propsStr = "";
    try { const p=JSON.parse(r.props); propsStr=Object.entries(p).map(([k,v])=>`<span class="tag">${k}:${v}</span>`).join(" "); } catch{}
    return `<tr><td class="event-name">${r.event}</td><td>${propsStr}</td><td>${r.session}</td><td class="ts">${r.ts}</td></tr>`;
  }).join("");
  document.getElementById("recent").innerHTML =
    `<table><thead><tr><th>Event</th><th>Properties</th><th>Session</th><th>Time</th></tr></thead><tbody>${rows}</tbody></table>`;
}

const SCREEN_NAMES = {
  "screen-upload":   "Upload screen",
  "screen-captions": "Captions screen",
  "screen-loading":  "Loading screen",
  "screen-success":  "Success screen",
  "screen-drafts":   "Drafts tab",
  "screen-settings": "Settings tab",
  "screen-welcome":  "Welcome screen",
};

function renderEntries(bodyId, data) {
  const tabName = bodyId.replace("-entries","");
  const totalEl = document.getElementById(tabName + "-total");
  const bodyEl  = document.getElementById(bodyId);
  if (!data || !Object.keys(data).length) {
    if (totalEl) totalEl.textContent = "0";
    bodyEl.innerHTML = '<div class="entry-empty">No data yet — populates after next user session.</div>';
    return;
  }
  const sorted = Object.entries(data).sort((a,b) => b[1]-a[1]);
  const total  = sorted.reduce((s,[,v]) => s+v, 0);
  const max    = Math.max(1, sorted[0][1]);
  if (totalEl) totalEl.textContent = total;
  const accent = tabName === "settings" ? "#b8405a" : "#5a8abf";
  bodyEl.innerHTML = sorted.map(([screen, n]) => {
    const label = SCREEN_NAMES[screen] || screen;
    const pct   = Math.round(n/max*100);
    const share = Math.round(n/total*100);
    return `<div class="entry-row">
      <div class="entry-label">${label}</div>
      <div class="entry-track"><div class="entry-fill" style="width:${pct}%;background:${accent};opacity:0.75"></div></div>
      <div class="entry-count">${n}</div>
      <div style="font-size:10px;color:#3a3a50;width:28px;flex-shrink:0;text-align:right">${share}%</div>
    </div>`;
  }).join("");
}

function renderFlow(d) {
  const panel = document.getElementById("flow-panel");
  const sv    = Object.assign({}, d.screen_views || {});
  const tabs  = d.tab_counts || {};
  const tr    = d.screen_transitions || [];
  const fn    = d.funnel || {};
  const draftSaved = d.draft_save_count || 0;

  // Merge tab switch counts into side nodes
  if (!sv["screen-drafts"])   sv["screen-drafts"]   = tabs["drafts"]   || 0;
  if (!sv["screen-settings"]) sv["screen-settings"] = tabs["settings"] || 0;

  // Fallback: populate from funnel events if no screen_view data yet
  const hasData = Object.values(sv).some(v => v > 0);
  if (!hasData) {
    sv["screen-welcome"]  = fn.app_open          || 0;
    sv["screen-upload"]   = fn.file_upload       || 0;
    sv["screen-loading"]  = fn.generate_success  || 0;
    sv["screen-captions"] = fn.caption_select    || 0;
    sv["screen-success"]  = fn.post_open         || 0;
  }

  const NW = 120, NH = 46, R = 8;
  const NODES = [
    {id:"screen-welcome",  x:10,  y:105, label:"Welcome",      main:true },
    {id:"screen-upload",   x:150, y:105, label:"Upload",       main:true },
    {id:"screen-loading",  x:290, y:105, label:"Loading",      main:true },
    {id:"screen-captions", x:430, y:105, label:"Captions",     main:true },
    {id:"screen-success",  x:570, y:105, label:"Success ✓",main:true },
    {id:"screen-drafts",          x:150, y:15,  label:"Drafts Tab",   main:false},
    {id:"settings-from-captions", x:430, y:15,  label:"Settings Tab", main:false, fixed: (d.tab_entries?.settings?.["screen-captions"]||0)},
    {id:"settings-from-upload",   x:150, y:205, label:"Settings Tab", main:false, fixed: (d.tab_entries?.settings?.["screen-upload"]||0)},
    {id:"draft-saved",            x:430, y:205, label:"Draft Saved",  main:false, fixed: draftSaved},
  ];

  const nodeMap = {};
  NODES.forEach(n => nodeMap[n.id] = n);

  const trMap = {};
  tr.forEach(t => { trMap[t.from + "→" + t.to] = t.n; });

  const counts = NODES.map(n => n.fixed !== undefined ? n.fixed : (sv[n.id]||0));
  const maxN = Math.max(1, ...counts);

  const ncx = n => n.x + NW/2;
  const ncy = n => n.y + NH/2;

  let lines = "", marks = "";

  function arrow(x1, y1, x2, y2, n, side) {
    const col = side ? "#3d3d58" : "#b8405a";
    const alpha = n ? Math.min(0.92, Math.max(0.22, n/maxN*0.9)) : 0.1;
    const sw = n ? Math.max(1, Math.min(2.5, n/maxN*2.5)) : 1;
    const mid = side ? "arr-s" : "arr-m";
    const dx = x2-x1, dy = y2-y1, len = Math.sqrt(dx*dx+dy*dy)||1;
    const ex = x2 - dx/len*9, ey = y2 - dy/len*9;
    lines += `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}" stroke="${col}" stroke-width="${sw.toFixed(1)}" stroke-opacity="${alpha.toFixed(2)}" marker-end="url(#${mid})"/>`;
    if (n) {
      const labX = ((x1+x2)/2).toFixed(1), labY = (y1===y2 ? y1-7 : (y1+y2)/2).toFixed(1);
      lines += `<text x="${labX}" y="${labY}" fill="${col}" fill-opacity="${Math.min(1,alpha+0.25).toFixed(2)}" font-size="10" text-anchor="middle" font-family="system-ui">${n}</text>`;
    }
  }

  // Main flow
  const mainSeq = ["screen-welcome","screen-upload","screen-loading","screen-captions","screen-success"];
  for (let i=0;i<mainSeq.length-1;i++) {
    const a = nodeMap[mainSeq[i]], b = nodeMap[mainSeq[i+1]];
    const n = trMap[a.id+"→"+b.id] || (!hasData ? (sv[b.id]||0) : 0);
    arrow(a.x+NW+2, ncy(a), b.x-2, ncy(b), n, false);
  }
  // Upload -> Drafts (straight up)
  { const a=nodeMap["screen-upload"], b=nodeMap["screen-drafts"];
    arrow(ncx(a), a.y, ncx(b), b.y+NH+2, sv["screen-drafts"]||0, true); }
  // Upload -> Settings (straight down)
  { const a=nodeMap["screen-upload"], b=nodeMap["settings-from-upload"];
    arrow(ncx(a), a.y+NH, ncx(b), b.y, d.tab_entries?.settings?.["screen-upload"]||0, true); }
  // Captions -> Settings (straight up)
  { const a=nodeMap["screen-captions"], b=nodeMap["settings-from-captions"];
    arrow(ncx(a), a.y, ncx(b), b.y+NH+2, d.tab_entries?.settings?.["screen-captions"]||0, true); }
  // Side: Captions -> Draft Saved (down)
  { const a=nodeMap["screen-captions"], b=nodeMap["draft-saved"];
    arrow(ncx(a), a.y+NH, ncx(b), b.y, draftSaved, true); }

  // Nodes
  const topN = sv["screen-welcome"] || sv["screen-upload"] || maxN || 1;
  NODES.forEach(node => {
    const n = node.fixed !== undefined ? node.fixed : (sv[node.id]||0);
    const on = n > 0;
    const fill   = node.main ? "#1a0e12" : "#111118";
    const stroke = on ? (node.main ? "#b8405a" : "#3d3d58") : "#1a1a24";
    const lblCol = on ? "#e8e8ea" : "#333340";
    const cntCol = on ? (node.main ? "#d4607c" : "#5a5a80") : "#252530";
    marks += `<rect x="${node.x}" y="${node.y}" width="${NW}" height="${NH}" rx="${R}" fill="${fill}" stroke="${stroke}" stroke-width="1.5" opacity="${on?1:0.5}"/>`;
    marks += `<text x="${ncx(node).toFixed(1)}" y="${(node.y+16).toFixed(1)}" fill="${lblCol}" font-size="11" font-weight="700" text-anchor="middle" font-family="system-ui,-apple-system">${node.label}</text>`;
    marks += `<text x="${ncx(node).toFixed(1)}" y="${(node.y+34).toFixed(1)}" fill="${cntCol}" font-size="15" font-weight="800" text-anchor="middle" font-family="system-ui,-apple-system">${on ? n : "—"}</text>`;
    if (node.main && node.id !== "screen-welcome" && on) {
      const pct = Math.round(n/topN*100);
      marks += `<text x="${ncx(node).toFixed(1)}" y="${(node.y+NH+13).toFixed(1)}" fill="#3d3d58" font-size="9.5" text-anchor="middle" font-family="system-ui">${pct}% reach</text>`;
    }
  });

  panel.innerHTML = `<svg viewBox="0 0 710 265" style="width:100%;min-width:360px;overflow:visible">
    <defs>
      <marker id="arr-m" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto"><path d="M0,0 L0,7 L7,3.5 z" fill="#b8405a"/></marker>
      <marker id="arr-s" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto"><path d="M0,0 L0,7 L7,3.5 z" fill="#3d3d58"/></marker>
    </defs>
    ${lines}${marks}
  </svg>`;
}

load();
setInterval(load, 30000);
</script>
</body>
</html>"""


@app.get("/analytics", response_class=HTMLResponse)
def analytics_dashboard(key: str = ""):
    if key != ANALYTICS_KEY:
        return HTMLResponse("<h3 style='font-family:sans-serif;padding:40px'>Access denied</h3>", status_code=403)
    return HTMLResponse(_DASHBOARD_HTML)


# --- Video/image helpers ---

MAX_B64_BYTES = 4 * 1024 * 1024

VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".m4v": "video/mp4",
}


def compress_to_b64(img_bytes: bytes, max_b64_bytes: int = MAX_B64_BYTES) -> str:
    """Resize + re-encode until the base64 output is under max_b64_bytes."""
    start_time = time.perf_counter()
    original_size = len(img_bytes)

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
            duration = time.perf_counter() - start_time
            log_data = {
                "event": "compress_to_b64",
                "original_bytes": original_size,
                "final_b64_bytes": len(b64),
                "duration_s": round(duration, 3),
            }
            log.info(json.dumps(log_data))
            return b64
        if quality > 55:
            quality -= 10
        else:
            scale *= 0.75


def upload_video_to_gemini(video_path: str, mime_type: str):
    """Upload video to Gemini File API and poll until ACTIVE."""
    uploaded = genai.upload_file(path=video_path, mime_type=mime_type)
    for _ in range(30):  # poll up to 60s
        f = genai.get_file(uploaded.name)
        if f.state.name == "ACTIVE":
            return f
        if f.state.name == "FAILED":
            raise RuntimeError("Gemini video processing failed")
        time.sleep(2)
    raise RuntimeError("Gemini video processing timed out")


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



GENRE_LABELS = {
    "auto": None,
    "pop": "Pop",
    "rnb": "R&B / Soul",
    "hiphop": "Hip-Hop / Rap",
    "indie": "Indie / Alternative",
    "electronic": "Electronic / Dance (EDM)",
    "chill": "Chill / Lo-fi / Ambient",
    "country": "Country / Folk",
    "latin": "Latin / Reggaeton",
    "kpop": "K-Pop",
    "house": "House / Deep House",
    "afrobeats": "Afrobeats",
    "lofi": "Lo-fi / Ambient",
    "jazz": "Jazz / Neo-Soul",
    "indiepop": "Indie Pop",
    "hyperpop": "Hyperpop",
}


def generate_content(media_parts: list, num_source_files: int = 1, tones: str = "", length_level: int = 2, hashtag_count: int = 5, music_genres: str = "auto", music_vibe: str = "", custom_phrases: str = "", emoji_style: str = "", emoji_intensity: int = 2) -> dict:
    store = load_store()
    style_block = build_style_block(store.get("example_captions", []))
    tone_guide = get_tone_guide(tones)
    length_guide = get_length_guide(length_level)
    hashtag_guide = get_hashtag_guide(min(hashtag_count, 5))
    genre_guide = get_genre_guide(music_genres, music_vibe)
    emoji_guide = get_emoji_guide(emoji_style, emoji_intensity)
    phrase_guide = get_custom_phrase_guide(custom_phrases)
    system = BRAND_CONTEXT + f"\n\n{tone_guide}\n\n{length_guide}\n{hashtag_guide}\n{emoji_guide}\n{genre_guide}{phrase_guide}" + style_block

    # media_parts is a list of PIL Images and/or Gemini file objects
    has_video = any(hasattr(p, "uri") for p in media_parts)
    parts = list(media_parts)

    if num_source_files > 1:
        media_word = "videos and images" if has_video else "images"
        image_context = (
            f"This is a carousel post with {num_source_files} {media_word}. "
            "Look at all of them together as a cohesive set — the common theme, mood, and story they tell together. "
            "Write captions that describe or celebrate the full set, not just a single item."
        )
    elif has_video:
        image_context = "Look closely at this video — analyze the subject, mood, content, motion, setting, and all visual details."
    else:
        image_context = "Look closely at this image — the subject, mood, colors, setting, and details."

    if hashtag_count == 0:
        hashtag_instruction = "Do NOT include any hashtags in any caption."
    else:
        tag_plural = "s" if hashtag_count > 1 else ""
        hashtag_instruction = f"End each caption with exactly {hashtag_count} niche-aware hashtag{tag_plural} on a new line — no more, no less."

    parts.append(
        f"{image_context} Write 3 Instagram captions. "
        "Match the creator's voice exactly if example captions are provided.\n\n"
        "Generate 3 distinct versions (each must match the LENGTH instruction exactly):\n"
        "1. Vibe Caption — mood-forward, emotionally aesthetic, dreamy.\n"
        "2. Hook Caption — POV/question/opening statement, strongest engagement potential.\n"
        "3. Story Caption — feels personal, believable lived moment, emotional realism.\n\n"
        "Each caption must feel like it was written by a real person — not an AI. "
        "Use natural rhythm, sentence fragments, internet-native phrasing. "
        f"{hashtag_instruction}\n\n"
        "For each caption suggest 3 real, currently trending songs (music_1/music_2/music_3) "
        "that match THAT caption's specific mood — distinctly different across the three captions. "
        "Only real songs with viral moments or high Reels/TikTok usage right now."
    )

    gemini_model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=CaptionOutput,
        ),
    )

    start_time = time.perf_counter()
    response = gemini_model.generate_content(parts)
    duration = time.perf_counter() - start_time

    out = CaptionOutput.model_validate_json(response.text)
    captions = [out.caption_1, out.caption_2, out.caption_3]
    music = {
        "1": [s.model_dump() for s in out.music_1],
        "2": [s.model_dump() for s in out.music_2],
        "3": [s.model_dump() for s in out.music_3],
    }

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    cost_usd = (input_tokens * 0.0000001) + (output_tokens * 0.0000004)

    log_data = {
        "event": "generate_content",
        "tones": tones,
        "music_genres": music_genres,
        "music_vibe": music_vibe,
        "emoji_style": emoji_style,
        "emoji_intensity": emoji_intensity,
        "num_source_files": num_source_files,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 5),
        "duration_s": round(duration, 3),
    }
    log.info(json.dumps(log_data))
    TOKEN_STATS["total_input"] += input_tokens
    TOKEN_STATS["total_output"] += output_tokens
    TOKEN_STATS["total_cost"] += cost_usd
    TOKEN_STATS["total_calls"] += 1

    return {"captions": captions, "music": music}


# --- Routes ---


@app.post("/generate-captions")
async def generate_captions_endpoint(files: list[UploadFile] = File(...), tones: str = Form(""), length_level: int = Form(2), hashtag_count: int = Form(3), music_genres: str = Form("auto"), music_vibe: str = Form(""), custom_phrases: str = Form(""), emoji_style: str = Form(""), emoji_intensity: int = Form(2)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    media_parts: list = []
    tmp_paths: list[str] = []
    uploaded_gemini_files: list = []

    for file in files:
        suffix = Path(file.filename).suffix.lower()
        is_video = suffix in VIDEO_MIME
        is_image = suffix in [".jpg", ".jpeg", ".png", ".webp"]
        if not is_video and not is_image:
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_paths.append(tmp.name)

        if is_video:
            gemini_file = upload_video_to_gemini(tmp.name, VIDEO_MIME[suffix])
            uploaded_gemini_files.append(gemini_file)
            media_parts.append(gemini_file)
        else:
            compressed_b64 = compress_to_b64(open(tmp.name, "rb").read())
            pil_img = Image.open(io.BytesIO(base64.b64decode(compressed_b64)))
            media_parts.append(pil_img)

    if not media_parts:
        raise HTTPException(status_code=400, detail="No supported files found")

    hashtag_count = min(hashtag_count, 5)
    start_time = time.perf_counter()
    log.info(json.dumps({
        "event": "generate_captions_start",
        "num_files": len(files),
        "num_media_parts": len(media_parts),
        "tones": tones,
        "length_level": length_level,
        "hashtag_count": hashtag_count,
        "music_genres": music_genres,
        "music_vibe": music_vibe,
        "custom_phrases": custom_phrases,
        "emoji_style": emoji_style,
        "emoji_intensity": emoji_intensity,
    }))

    try:
        result = generate_content(media_parts, num_source_files=len(files), tones=tones, length_level=length_level, hashtag_count=hashtag_count, music_genres=music_genres, music_vibe=music_vibe, custom_phrases=custom_phrases, emoji_style=emoji_style, emoji_intensity=emoji_intensity)
        duration = time.perf_counter() - start_time
        log.info(
            json.dumps(
                {
                    "event": "generate_captions_success",
                    "duration_s": round(duration, 3),
                    "num_captions": len(result.get("captions", [])),
                }
            )
        )
        return result
    except Exception as e:
        duration = time.perf_counter() - start_time
        error_log = {
            "event": "generate_captions_error",
            "error": str(e),
            "duration_s": round(duration, 3),
        }
        log.error(json.dumps(error_log), exc_info=True)
        LOG_ENTRIES.append(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "method": "POST",
                "path": "/generate-captions",
                "status": 500,
                "duration_s": round(duration, 3),
                "error": str(e),
            }
        )
        err_str = str(e)
        # Surface Gemini API key errors clearly
        if "api_key" in err_str.lower() or "api key" in err_str.lower() or "permission" in err_str.lower() or "credential" in err_str.lower():
            raise HTTPException(status_code=500, detail="AI service error: invalid or missing GEMINI_API_KEY")
        raise HTTPException(status_code=500, detail=err_str[:200])
    finally:
        for p in tmp_paths:
            try:
                os.unlink(p)
            except:
                pass
        for gf in uploaded_gemini_files:
            try:
                genai.delete_file(gf.name)
            except:
                pass


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
        raise HTTPException(
            status_code=400,
            detail="Instagram not connected. Add your access token first.",
        )

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
        {
            "id": p["id"],
            "name": p.get("formatted_username", p.get("service_username", "Instagram")),
        }
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
    log.info(
        json.dumps({"event": "buffer_connected", "profile_id": payload.profile_id})
    )

    # auto-sync Instagram captions to train Claude on their voice
    if payload.access_token and payload.profile_id:
        try:
            ig_captions = await _fetch_ig_captions_from_buffer(
                payload.access_token, payload.profile_id
            )
            if ig_captions:
                store["example_captions"] = ig_captions
                save_store(store)
                log.info(
                    json.dumps(
                        {
                            "event": "buffer_auto_sync_captions_success",
                            "num_captions": len(ig_captions),
                        }
                    )
                )
        except Exception as e:
            log.warning(
                json.dumps(
                    {"event": "buffer_auto_sync_captions_failed", "error": str(e)}
                )
            )

    return {"status": "saved"}


class BufferTokenWithUsername(BufferTokenPayload):
    username: str = ""


@app.get("/settings/buffer")
async def get_buffer_status():
    store = load_store()
    connected = bool(
        store.get("buffer_access_token") and store.get("buffer_profile_id")
    )
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
        raise HTTPException(
            status_code=400,
            detail="Buffer not connected. Add your Buffer token in settings.",
        )

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
    params = urlencode(
        {
            "client_id": META_APP_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": IG_SCOPES,
            "response_type": "code",
            "state": state,
        }
    )
    return RedirectResponse(f"https://www.facebook.com/dialog/oauth?{params}")


@app.get("/auth/callback")
async def instagram_callback(code: str = None, error: str = None):
    """Handle OAuth callback from Meta."""
    if error or not code:
        log.error(json.dumps({"event": "instagram_oauth_error", "error": str(error)}))
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
        log.error(
            json.dumps(
                {
                    "event": "instagram_token_exchange_failed",
                    "error": token_res.text,
                    "status_code": token_res.status_code,
                }
            )
        )
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
            params={
                "access_token": access_token,
                "fields": "id,name,instagram_business_account",
            },
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
                    params={
                        "fields": "caption",
                        "access_token": access_token,
                        "limit": 20,
                    },
                )
            if media_res.status_code == 200:
                captions = [
                    p["caption"]
                    for p in media_res.json().get("data", [])
                    if p.get("caption", "").strip()
                ]
                if captions:
                    store["example_captions"] = captions
                    save_store(store)
                    log.info(
                        json.dumps(
                            {
                                "event": "instagram_auto_sync_captions_success",
                                "num_captions": len(captions),
                                "username": ig_username,
                            }
                        )
                    )
        except Exception as e:
            log.warning(
                json.dumps({"event": "instagram_caption_sync_failed", "error": str(e)})
            )

    log.info(
        json.dumps(
            {
                "event": "instagram_connected",
                "username": ig_username,
                "user_id": ig_user_id,
            }
        )
    )
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
    log.info(
        json.dumps(
            {
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_s": round(duration, 3),
            }
        )
    )
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
    """Proxy music preview search — tries iTunes then Deezer for broader coverage."""
    async with httpx.AsyncClient(timeout=8) as c:

        async def itunes(term: str):
            r = await c.get(
                "https://itunes.apple.com/search",
                params={"term": term, "media": "music", "limit": 5},
            )
            hit = next(
                (x for x in r.json().get("results", []) if x.get("previewUrl")), None
            )
            return hit["previewUrl"] if hit else None

        async def deezer(term: str):
            r = await c.get(
                "https://api.deezer.com/search", params={"q": term, "limit": 5}
            )
            hit = next((x for x in r.json().get("data", []) if x.get("preview")), None)
            return hit["preview"] if hit else None

        full = f"{artist} {song}"
        url = (
            await itunes(full)
            or await itunes(song)
            or await deezer(full)
            or await deezer(song)
        )
        return {"previewUrl": url}


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
