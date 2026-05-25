const API_URL = "https://socialmediaagent-production-83c2.up.railway.app";

// ── Analytics ──
const SESSION_ID = (() => {
  let id = sessionStorage.getItem("cap_sid");
  if (!id) { id = Math.random().toString(36).slice(2) + Date.now().toString(36); sessionStorage.setItem("cap_sid", id); }
  return id;
})();

function track(event, props = {}) {
  fetch(`${API_URL}/analytics/event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: SESSION_ID, event, props }),
  }).catch(() => {});
}

// ── Sound system (Web Audio API — no files needed) ──
let audioCtx = null;

// Minimal silent WAV — used to unlock <audio> elements on iOS.
// iOS only unlocks an element when play() *succeeds*, so we need a real src.
const SILENT_SRC = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAESsAAABAAgAZGF0YQAAAAA=";

const cardAudio = new Audio(); // for music card ▶ previews
const trimAudio = new Audio(); // for trim panel

function getAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

// Unlock AudioContext + both <audio> elements on first touch (capture fires before click).
(function iosAudioUnlock() {
  function unlock() {
    // AudioContext unlock
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state !== "running") {
      audioCtx.resume().then(() => {
        const buf = audioCtx.createBuffer(1, 1, audioCtx.sampleRate);
        const src = audioCtx.createBufferSource();
        src.buffer = buf;
        src.connect(audioCtx.destination);
        src.start(0);
      }).catch(() => {});
    }
    // HTML Audio element unlock — must play a real src so iOS marks them as user-activated
    [cardAudio, trimAudio].forEach(a => {
      a.src = SILENT_SRC;
      a.play().then(() => { a.pause(); a.currentTime = 0; }).catch(() => {});
    });
  }
  document.addEventListener("touchstart", unlock, { capture: true, passive: true, once: true });
  document.addEventListener("click",      unlock, { capture: true, once: true });
})();

function playSound(type) {
  try {
    const ctx = getAudio();
    const master = ctx.createGain();
    master.gain.setValueAtTime(0.18, ctx.currentTime);
    master.connect(ctx.destination);

    switch (type) {

      case "click": {
        // soft tick
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(master);
        o.type = "sine";
        o.frequency.setValueAtTime(600, ctx.currentTime);
        o.frequency.exponentialRampToValueAtTime(400, ctx.currentTime + 0.08);
        g.gain.setValueAtTime(0.5, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);
        o.start(); o.stop(ctx.currentTime + 0.08);
        break;
      }

      case "upload": {
        // rising chime
        [0, 0.08, 0.16].forEach((delay, i) => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.connect(g); g.connect(master);
          o.type = "sine";
          o.frequency.setValueAtTime([440, 554, 659][i], ctx.currentTime + delay);
          g.gain.setValueAtTime(0.4, ctx.currentTime + delay);
          g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.3);
          o.start(ctx.currentTime + delay);
          o.stop(ctx.currentTime + delay + 0.3);
        });
        break;
      }

      case "generate": {
        // magical shimmer sweep
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(master);
        o.type = "sine";
        o.frequency.setValueAtTime(300, ctx.currentTime);
        o.frequency.exponentialRampToValueAtTime(900, ctx.currentTime + 0.4);
        g.gain.setValueAtTime(0.3, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        o.start(); o.stop(ctx.currentTime + 0.4);
        break;
      }

      case "caption-select": {
        // soft pop
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(master);
        o.type = "sine";
        o.frequency.setValueAtTime(520, ctx.currentTime);
        o.frequency.exponentialRampToValueAtTime(340, ctx.currentTime + 0.12);
        g.gain.setValueAtTime(0.4, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
        o.start(); o.stop(ctx.currentTime + 0.12);
        break;
      }

      case "success": {
        // victory chime — 4 ascending notes
        [0, 0.1, 0.2, 0.32].forEach((delay, i) => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.connect(g); g.connect(master);
          o.type = "sine";
          o.frequency.setValueAtTime([523, 659, 784, 1047][i], ctx.currentTime + delay);
          g.gain.setValueAtTime(0.45, ctx.currentTime + delay);
          g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.35);
          o.start(ctx.currentTime + delay);
          o.stop(ctx.currentTime + delay + 0.35);
        });
        break;
      }

      case "swipe": {
        // screen transition whoosh
        const bufSize = ctx.sampleRate * 0.15;
        const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / bufSize);
        const src = ctx.createBufferSource();
        const filter = ctx.createBiquadFilter();
        const g = ctx.createGain();
        filter.type = "bandpass";
        filter.frequency.setValueAtTime(800, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(2400, ctx.currentTime + 0.15);
        src.buffer = buf;
        src.connect(filter); filter.connect(g); g.connect(master);
        g.gain.setValueAtTime(0.6, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
        src.start(); src.stop(ctx.currentTime + 0.15);
        break;
      }

      case "music-copy": {
        // quick double-tick
        [0, 0.07].forEach(delay => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.connect(g); g.connect(master);
          o.type = "sine";
          o.frequency.setValueAtTime(880, ctx.currentTime + delay);
          g.gain.setValueAtTime(0.35, ctx.currentTime + delay);
          g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.08);
          o.start(ctx.currentTime + delay);
          o.stop(ctx.currentTime + delay + 0.08);
        });
        break;
      }
    }
  } catch {}
}

// ── Sakura tree canvas ──
(function () {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let W, H, branches, blossomClusters, fallingPetals, growProg = 0, lastT = 0;

  const DEPTH = 8;
  const PETAL_COLORS = [
    [255, 218, 230], [248, 198, 214], [255, 232, 240],
    [238, 182, 204], [252, 208, 224], [255, 242, 246],
  ];

  function buildTree() {
    branches = [];
    blossomClusters = [];
    fallingPetals = [];
    growProg = 0;

    const cx = W * 0.48, cy = H + 2;
    const trunkLen = H * 0.24;

    function addBranch(x1, y1, ang, len, depth) {
      if (depth === 0 || len < 3) return;
      const x2 = x1 + Math.sin(ang) * len;
      const y2 = y1 - Math.cos(ang) * len;
      const t = (DEPTH - depth) / (DEPTH - 1); // 0=trunk … 1=tips
      branches.push({ x1, y1, x2, y2, t,
        width: Math.max(0.6, (1 - t) * 11 + 0.6),
        r: Math.round(52 + t * 78), g: Math.round(28 + t * 40), b: Math.round(14 + t * 22),
        opacity: 0.88 - t * 0.28,
      });

      if (depth === 1) {
        const n = 5 + Math.floor(Math.random() * 5);
        for (let i = 0; i < n; i++) {
          const c = PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)];
          blossomClusters.push({
            x: x2 + (Math.random() - 0.5) * 20,
            y: y2 + (Math.random() - 0.5) * 20,
            r: 3 + Math.random() * 4.5,
            alpha: 0, targetAlpha: 0.75 + Math.random() * 0.25, c,
            wobble: Math.random() * Math.PI * 2,
          });
        }
        return;
      }

      const spread = 0.28 + Math.random() * 0.20;
      const lf     = 0.60 + Math.random() * 0.12;
      const jit    = () => (Math.random() - 0.5) * 0.07;
      addBranch(x2, y2, ang - spread + jit(), len * lf, depth - 1);
      addBranch(x2, y2, ang + spread + jit(), len * lf, depth - 1);
      if (depth > 3 && Math.random() > 0.52)
        addBranch(x2, y2, ang + jit() * 3, len * (0.42 + Math.random() * 0.1), depth - 2);
    }

    addBranch(cx, cy, 0, trunkLen, DEPTH);
    branches.sort((a, b) => a.t - b.t); // trunk first
    fallingPetals = Array.from({ length: 28 }, () => newFallingPetal(true));
  }

  function newFallingPetal(scatter) {
    const z = 0.25 + Math.random() * 0.75;
    return {
      x: Math.random() * W,
      y: scatter ? Math.random() * H : -(10 + Math.random() * 30),
      z, size: 3.5 + z * 9,
      vy: 0.35 + z * 1.1,
      vx: (Math.random() - 0.5) * 0.6,
      rot: Math.random() * Math.PI * 2,
      rotV: (Math.random() - 0.5) * 0.035,
      swayPh: Math.random() * Math.PI * 2,
      swayF: 0.35 + Math.random() * 0.55,
      alpha: 0.28 + z * 0.48,
      c: PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)],
    };
  }

  function drawFallingPetal(p) {
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate(p.rot);
    ctx.globalAlpha = p.alpha;
    for (let i = 0; i < 5; i++) {
      ctx.save();
      ctx.rotate(i * Math.PI * 2 / 5);
      ctx.beginPath();
      ctx.ellipse(0, -p.size * 0.54, p.size * 0.27, p.size * 0.54, 0, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.c.join(",")},1)`;
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    buildTree();
  }

  function animate(t) {
    const dt = Math.min((t - lastT) / 1000, 0.05);
    lastT = t;
    ctx.clearRect(0, 0, W, H);

    // Tree grows over ~3.8 s
    if (growProg < 1) growProg = Math.min(1, growProg + dt * 0.26);

    // ── Branches ──
    ctx.lineCap = "round";
    branches.forEach(b => {
      // staggered: trunk at growProg=0, tips at growProg≈0.82
      const localProg = Math.max(0, Math.min(1, (growProg - b.t * 0.80) / 0.20));
      if (localProg <= 0) return;
      const ex = b.x1 + (b.x2 - b.x1) * localProg;
      const ey = b.y1 + (b.y2 - b.y1) * localProg;
      ctx.beginPath();
      ctx.moveTo(b.x1, b.y1);
      ctx.lineTo(ex, ey);
      ctx.lineWidth = b.width;
      ctx.strokeStyle = `rgba(${b.r},${b.g},${b.b},${b.opacity})`;
      ctx.stroke();
    });

    // ── Blossoms ──
    const blossomTarget = Math.max(0, (growProg - 0.68) / 0.32);
    blossomClusters.forEach(bl => {
      bl.alpha += (bl.targetAlpha * blossomTarget - bl.alpha) * 0.04;
      if (bl.alpha < 0.01) return;
      bl.wobble += 0.008;
      const wx = Math.sin(bl.wobble) * 0.4;
      ctx.save();
      ctx.translate(bl.x + wx, bl.y);
      ctx.globalAlpha = bl.alpha;
      for (let i = 0; i < 5; i++) {
        ctx.save();
        ctx.rotate(i * Math.PI * 2 / 5);
        ctx.beginPath();
        ctx.ellipse(0, -bl.r * 0.62, bl.r * 0.36, bl.r * 0.62, 0, 0, Math.PI * 2);
        ctx.fillStyle = `rgb(${bl.c.join(",")})`;
        ctx.fill();
        ctx.restore();
      }
      ctx.beginPath();
      ctx.arc(0, 0, bl.r * 0.22, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,242,248,0.95)";
      ctx.fill();
      ctx.restore();
    });

    // ── Falling petals (after tree starts blooming) ──
    if (growProg > 0.35) {
      const petalOpacity = Math.min(1, (growProg - 0.35) / 0.25);
      fallingPetals.forEach((p, i) => {
        p.y  += p.vy;
        p.x  += p.vx + Math.sin(t * 0.001 * p.swayF + p.swayPh) * 0.55;
        p.rot += p.rotV;
        if (p.y > H + 24 || p.x < -40 || p.x > W + 40)
          fallingPetals[i] = newFallingPetal(false);
        ctx.globalAlpha = p.alpha * petalOpacity;
        drawFallingPetal(p);
      });
    }

    ctx.globalAlpha = 1;
    requestAnimationFrame(animate);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(t => { lastT = t; animate(t); });
})();

// ── Ripple effect on buttons ──
document.addEventListener("click", e => {
  const btn = e.target.closest(".btn-primary, .btn-secondary, .btn-instagram");
  if (!btn) return;
  playSound("click");
  const r = document.createElement("span");
  r.className = "ripple-effect";
  r.style.left = `${e.clientX - btn.getBoundingClientRect().left}px`;
  r.style.top = `${e.clientY - btn.getBoundingClientRect().top}px`;
  btn.appendChild(r);
  setTimeout(() => r.remove(), 700);
});

// ── Confetti burst on success ──
function launchConfetti() {
  const colors = ["#f7c5d2", "#e8b97a", "#c8e6c8", "#d4607c", "#ffffff", "#f0dde5"];
  for (let i = 0; i < 32; i++) {
    const c = document.createElement("div");
    c.className = "confetti";
    c.style.cssText = `
      left: ${20 + Math.random() * 60}%;
      top: 30%;
      background: ${colors[Math.floor(Math.random() * colors.length)]};
      animation-delay: ${Math.random() * 0.4}s;
      animation-duration: ${0.9 + Math.random() * 0.6}s;
      transform: rotate(${Math.random() * 360}deg);
    `;
    document.body.appendChild(c);
    setTimeout(() => c.remove(), 1800);
  }
}

// ── Animated screen transitions ──
const CREATE_SCREENS = new Set(["screen-upload","screen-captions","screen-loading","screen-success"]);

function showScreen(id) {
  playSound("swipe");
  document.querySelectorAll(".screen").forEach(s => {
    if (!s.classList.contains("hidden")) {
      s.classList.add("hidden");
    }
  });
  const next = document.getElementById(id);
  next.classList.remove("hidden");
  next.classList.remove("enter");
  void next.offsetWidth;
  next.classList.add("enter");
  if (CREATE_SCREENS.has(id)) lastCreateScreen = id;
}

const CAPTION_LABELS = ["Casual", "Engaging", "Call to Action"];

let selectedFiles = [];
let selectedCaption = "";
let selectedTones = new Set(); // empty = auto
let selectedLengthLevel = 2;
let selectedHashtagCount = 3;
let selectedGenres = new Set(["auto"]);
let musicVibe = "";
let customPhrases = "";
let emojiStyle = "";
let emojiIntensity = 2;

// Vibe pill multi-select
document.querySelectorAll(".tone-pill:not(.genre-pill)").forEach(pill => {
  pill.addEventListener("click", () => {
    pill.classList.toggle("active");
    if (pill.classList.contains("active")) {
      selectedTones.add(pill.dataset.tone);
      track("tone_select", { tone: pill.dataset.tone });
    } else {
      selectedTones.delete(pill.dataset.tone);
    }
    playSound("click");
  });
});

// Vibe search filter
document.getElementById("vibe-search").addEventListener("input", e => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll(".tone-pill:not(.genre-pill)").forEach(pill => {
    const label = pill.textContent.toLowerCase();
    pill.style.display = !q || label.includes(q) ? "" : "none";
  });
});

// Genre pill multi-select
document.querySelectorAll(".genre-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    const genre = pill.dataset.genre;
    if (genre === "auto") {
      selectedGenres.clear();
      selectedGenres.add("auto");
      document.querySelectorAll(".genre-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
    } else {
      selectedGenres.delete("auto");
      document.querySelector(".genre-pill[data-genre='auto']").classList.remove("active");
      if (selectedGenres.has(genre)) {
        selectedGenres.delete(genre);
        pill.classList.remove("active");
        if (selectedGenres.size === 0) {
          selectedGenres.add("auto");
          document.querySelector(".genre-pill[data-genre='auto']").classList.add("active");
        }
      } else {
        selectedGenres.add(genre);
        pill.classList.add("active");
        track("genre_select", { genre });
      }
    }
    playSound("click");
  });
});

// Genre search filter
document.getElementById("genre-search").addEventListener("input", e => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll(".genre-pill").forEach(pill => {
    const label = pill.textContent.toLowerCase();
    pill.style.display = !q || label.includes(q) ? "" : "none";
  });
});

// Music vibe input
document.getElementById("music-vibe-input").addEventListener("input", e => {
  musicVibe = e.target.value;
});

// Custom phrases
document.getElementById("custom-phrases-input").addEventListener("input", e => {
  customPhrases = e.target.value;
});

// Length slider
const LENGTH_LABELS = { 1: "Micro", 2: "Short", 3: "Medium", 4: "Long", 5: "Story" };
const lengthSlider = document.getElementById("length-slider");
const lengthValLabel = document.getElementById("length-val-label");

function updateLengthSlider() {
  selectedLengthLevel = parseInt(lengthSlider.value);
  lengthValLabel.textContent = LENGTH_LABELS[selectedLengthLevel];
  const pct = ((selectedLengthLevel - 1) / 4) * 100;
  lengthSlider.style.setProperty("--fill", pct + "%");
}
lengthSlider.addEventListener("input", updateLengthSlider);
updateLengthSlider();

// Hashtag slider
const hashtagSlider = document.getElementById("hashtag-slider");
const hashtagValLabel = document.getElementById("hashtag-val-label");

function updateHashtagSlider() {
  selectedHashtagCount = parseInt(hashtagSlider.value);
  hashtagValLabel.textContent = selectedHashtagCount === 0 ? "None" : `${selectedHashtagCount} tags`;
  const pct = (selectedHashtagCount / 5) * 100;
  hashtagSlider.style.setProperty("--fill", pct + "%");
}
hashtagSlider.addEventListener("input", updateHashtagSlider);
updateHashtagSlider();

// Emoji presets
document.querySelectorAll(".emoji-preset").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".emoji-preset").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    emojiStyle = btn.dataset.style;
    emojiIntensity = parseInt(btn.dataset.intensity);
    const emojiSliderEl = document.getElementById("emoji-slider");
    emojiSliderEl.value = emojiIntensity;
    updateEmojiSlider();
    playSound("click");
  });
});

const EMOJI_INTENSITY_LABELS = { 0: "None", 1: "Minimal", 2: "Moderate", 3: "Expressive" };
const emojiSlider = document.getElementById("emoji-slider");
const emojiValLabel = document.getElementById("emoji-val-label");

function updateEmojiSlider() {
  emojiIntensity = parseInt(emojiSlider.value);
  emojiValLabel.textContent = EMOJI_INTENSITY_LABELS[emojiIntensity];
  const pct = (emojiIntensity / 3) * 100;
  emojiSlider.style.setProperty("--fill", pct + "%");
}
emojiSlider.addEventListener("input", updateEmojiSlider);
updateEmojiSlider();

// Keep backend warm
setInterval(() => fetch(`${API_URL}/health`).catch(() => {}), 240000);

// Set login URL
const _igBtn = document.getElementById("btn-instagram-login");
_igBtn.href = `${API_URL}/auth/instagram`;
_igBtn.addEventListener("click", () => track("instagram_connect_start"));

// On load — open to everyone, check if already connected
async function initApp() {
  const urlParams = new URLSearchParams(window.location.search);
  const authResult = urlParams.get("auth");
  const username = urlParams.get("username");
  if (authResult) history.replaceState({}, "", window.location.pathname);

  if (authResult === "success" && username) {
    enterApp(username);
    return;
  }

  if (authResult === "error") {
    alert("Instagram connection failed. Make sure you have a Creator or Business account.");
  }

  // check if already connected from a previous session
  try {
    const res = await fetch(`${API_URL}/auth/status`);
    const data = await res.json();
    if (data.connected) {
      enterApp(data.username);
      return;
    }
  } catch {}

  showScreen("screen-welcome");
}

document.getElementById("btn-try-now").addEventListener("click", () => {
  enterApp(null);
});

// iOS install banner — show once on iOS Safari when not already installed as PWA
(function () {
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone = window.navigator.standalone;
  const dismissed = sessionStorage.getItem("install-banner-dismissed");
  if (!isIos || isStandalone || dismissed) return;

  const banner = document.getElementById("ios-install-banner");
  setTimeout(() => banner.classList.remove("hidden"), 2000);

  document.getElementById("ios-install-close").addEventListener("click", () => {
    banner.classList.add("hidden");
    sessionStorage.setItem("install-banner-dismissed", "1");
  });
})();

let activeTab = "create";
let lastCreateScreen = "screen-upload";

function setActiveTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
}

track("app_open", { has_username: !!localStorage.getItem("cap_sid") });

function enterApp(username) {
  document.getElementById("main-header").classList.remove("hidden");
  document.getElementById("tab-bar").classList.remove("hidden");
  const pill = document.getElementById("user-pill");
  const connectedName = document.getElementById("connected-name");

  if (username) {
    pill.textContent = `⚡ @${username}`;
    pill.classList.remove("hidden");
    connectedName.textContent = `@${username}`;
    document.getElementById("setup-connect").classList.add("hidden");
    document.getElementById("setup-connected").classList.remove("hidden");
  }

  showScreen("screen-upload");
  setActiveTab("create");
}

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    setActiveTab(tab);
    if (tab === "create") {
      showScreen(lastCreateScreen);
    } else if (tab === "drafts") {
      renderCalendar();
      renderDrafts();
      showScreen("screen-drafts");
    } else if (tab === "settings") {
      showScreen("screen-settings");
      loadSettingsData();
    }
    playSound("click");
    track("tab_switch", { tab });
  });
});

initApp();

// Fetch with timeout + retry
async function fetchWithRetry(url, options = {}, retries = 2, timeoutMs = 60000) {
  for (let i = 0; i <= retries; i++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timer);
      return res;
    } catch (err) {
      clearTimeout(timer);
      if (i === retries) throw err;
      await new Promise(r => setTimeout(r, 1500));
    }
  }
}

// Elements
const uploadArea = document.getElementById("upload-area");
const fileInput = document.getElementById("file-input");
const previewWrap = document.getElementById("preview-wrap");
const btnClear = document.getElementById("btn-clear");
const btnGenerate = document.getElementById("btn-generate");
const captionList = document.getElementById("caption-list");
const captionEdit = document.getElementById("caption-edit");
const selectedWrap = document.getElementById("selected-wrap");
const btnPost = document.getElementById("btn-post");
const btnBack = document.getElementById("btn-back");
const btnNew = document.getElementById("btn-new");

// Upload interactions
uploadArea.addEventListener("click", () => fileInput.click());

uploadArea.addEventListener("dragover", e => {
  e.preventDefault();
  uploadArea.classList.add("drag-over");
});

uploadArea.addEventListener("dragleave", () => {
  uploadArea.classList.remove("drag-over");
});

uploadArea.addEventListener("drop", e => {
  e.preventDefault();
  uploadArea.classList.remove("drag-over");
  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    addFiles(fileInput.files);
    fileInput.value = "";
  }
});

function addFiles(fileList) {
  const valid = Array.from(fileList).filter(
    f => f.type.startsWith("image/") || f.type.startsWith("video/")
  );
  selectedFiles = [...selectedFiles, ...valid].slice(0, 10);
  renderCarousel();
  if (selectedFiles.length) {
    playSound("upload");
    track("file_upload", {
      count: selectedFiles.length,
      has_video: selectedFiles.some(f => f.type.startsWith("video/")),
    });
  }
}

function renderCarousel() {
  const strip = document.getElementById("carousel-strip");
  const countEl = document.getElementById("carousel-count");
  if (!strip || !countEl) return;
  strip.innerHTML = "";

  selectedFiles.forEach((file, idx) => {
    const thumb = document.createElement("div");
    thumb.className = "carousel-thumb";

    const url = URL.createObjectURL(file);
    if (file.type.startsWith("video/")) {
      const vid = document.createElement("video");
      vid.src = url; vid.muted = true; vid.playsInline = true;
      thumb.appendChild(vid);
      const badge = document.createElement("span");
      badge.className = "carousel-thumb-badge";
      badge.textContent = "▶ video";
      thumb.appendChild(badge);
    } else {
      const img = document.createElement("img");
      img.src = url;
      thumb.appendChild(img);
    }

    const rmBtn = document.createElement("button");
    rmBtn.className = "carousel-thumb-remove";
    rmBtn.textContent = "✕";
    rmBtn.addEventListener("click", e => {
      e.stopPropagation();
      playSound("click");
      selectedFiles.splice(idx, 1);
      if (!selectedFiles.length) {
        previewWrap.classList.add("hidden");
        uploadArea.classList.remove("hidden");
        btnGenerate.disabled = true;
      } else {
        renderCarousel();
      }
    });
    thumb.appendChild(rmBtn);
    strip.appendChild(thumb);
  });

  if (selectedFiles.length < 10) {
    const addBtn = document.createElement("div");
    addBtn.className = "carousel-add";
    addBtn.innerHTML = `<span class="carousel-add-icon">+</span><span class="carousel-add-label">Add</span>`;
    addBtn.addEventListener("click", () => fileInput.click());
    strip.appendChild(addBtn);
  }

  const n = selectedFiles.length;
  countEl.textContent = n === 1 ? "Single post" : `${n} photos — carousel post`;

  uploadArea.classList.add("hidden");
  previewWrap.classList.remove("hidden");
  btnGenerate.disabled = false;
}

function clearFiles() {
  selectedFiles = [];
  previewWrap.classList.add("hidden");
  uploadArea.classList.remove("hidden");
  btnGenerate.disabled = true;
  fileInput.value = "";
}

btnClear.addEventListener("click", clearFiles);

async function generateCaptions() {
  if (!selectedFiles.length) return;

  playSound("generate");
  showScreen("screen-loading");
  track("generate_start", {
    tones: Array.from(selectedTones).join(","),
    genres: Array.from(selectedGenres).join(","),
    length: selectedLengthLevel,
    hashtags: selectedHashtagCount,
    file_count: selectedFiles.length,
  });

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append("files", f));
  formData.append("tones", Array.from(selectedTones).join(","));
  formData.append("length_level", selectedLengthLevel);
  formData.append("hashtag_count", selectedHashtagCount);
  formData.append("music_genres", Array.from(selectedGenres).join(","));
  formData.append("music_vibe", musicVibe);
  formData.append("custom_phrases", customPhrases);
  formData.append("emoji_style", emojiStyle);
  formData.append("emoji_intensity", emojiIntensity);

  const loaderText = document.getElementById("loader-text");
  const isCarousel = selectedFiles.length > 1;
  const toneLabelMap = {
    aesthetic: "the aesthetic", bold: "bold energy",
    relatable: "the feels", romantic: "the romance", motivational: "the motivation",
    wanderlust: "wanderlust", funny: "the humor", earthy: "the earthy vibe",
    hustle: "hustle mode", moody: "the mood", foodie: "the dish",
    cinematic: "the cinematic vibe", luxury: "the luxury aesthetic",
    soft: "soft energy", chaotic: "the chaos", mysterious: "the mystery",
  };
  const firstTone = Array.from(selectedTones)[0];
  const toneLabel = (firstTone && toneLabelMap[firstTone]) || "the vibe";
  const messages = [
    "Reading your content...",
    isCarousel ? `Analyzing ${selectedFiles.length} photos...` : "Catching the aesthetic...",
    `Writing captions for ${toneLabel}...`,
  ];
  let msgIdx = 0;
  const msgInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % messages.length;
    loaderText.textContent = messages[msgIdx];
  }, 3000);

  try {
    const res = await fetchWithRetry(`${API_URL}/generate-captions`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    clearInterval(msgInterval);
    allMusic = data.music || {};
    renderCaptions(data.captions);
    showScreen("screen-captions");
    track("generate_success", { level: selectedLengthLevel });
  } catch (err) {
    clearInterval(msgInterval);
    track("generate_error", { error: (err.message || "unknown").slice(0, 80) });
    const msg = err.name === "AbortError"
      ? "Taking too long — try a smaller photo or video."
      : (err.message || "Could not reach the server. Check your connection and try again.").slice(0, 200);
    alert(msg);
    showScreen("screen-upload");
  }
}

btnGenerate.addEventListener("click", generateCaptions);
document.getElementById("btn-refresh").addEventListener("click", generateCaptions);


let allMusic = {};          // keyed by "1","2","3" — per-caption music sets
let currentMusicItems = [];
let currentPreviewBtn = null;
let previewMusicTrack = null;
let previewMusicUrl = null;
let selectedMusicCardEl = null;
const musicUrlCache = {}; // keyed by "Artist - Song"

async function prefetchMusicUrls(tracks) {
  for (const t of tracks) {
    const key = `${t.artist} - ${t.song}`;
    if (musicUrlCache[key] !== undefined) continue;
    musicUrlCache[key] = "loading";
    try {
      const params = new URLSearchParams({ artist: t.artist, song: t.song });
      const res = await fetch(`${API_URL}/music-preview?${params}`);
      const data = await res.json();
      musicUrlCache[key] = data.previewUrl || null;
    } catch {
      musicUrlCache[key] = null;
    }
  }
}

function renderMusic(music) {
  currentMusicItems = music ? [...music] : [];
  _drawMusicList();
  prefetchMusicUrls(currentMusicItems); // background — no await
}

function _drawMusicList() {
  const wrap = document.getElementById("music-wrap");
  const list = document.getElementById("music-list");
  list.innerHTML = "";

  if (!currentMusicItems.length) {
    wrap.classList.add("hidden");
    return;
  }

  currentMusicItems.forEach((track, i) => {
    const el = document.createElement("div");
    el.className = "music-card";

    const song = track.song.replace(/"/g, "&quot;");
    const artist = track.artist.replace(/"/g, "&quot;");
    el.innerHTML = `
      <div class="music-num">${i + 1}</div>
      <div class="music-info">
        <div class="music-song">${track.song}</div>
        <div class="music-artist">${track.artist}</div>
      </div>
      <button class="music-preview" title="Preview 30s">▶</button>
      <button class="music-copy" title="Copy" data-text="${artist} - ${song}">⎘</button>
      <button class="music-add-preview" title="Add to post preview">+ Use</button>
    `;

    const previewBtn = el.querySelector(".music-preview");
    previewBtn.addEventListener("click", () => {
      handlePreview(previewBtn, track.artist, track.song);
      track("music_preview", { artist: track.artist, song: track.song });
    });

    el.querySelector(".music-copy").addEventListener("click", async (e) => {
      playSound("music-copy");
      const text = e.currentTarget.dataset.text;
      try { await navigator.clipboard.writeText(text); } catch {}
      e.currentTarget.textContent = "✓";
      setTimeout(() => e.currentTarget.textContent = "⎘", 2000);
    });

    el.querySelector(".music-add-preview").addEventListener("click", () => {
      addMusicToPreview(el, track.artist, track.song);
    });

    list.appendChild(el);
  });

  wrap.classList.remove("hidden");
}

function handlePreview(btn, artist, song) {
  // Toggle play/pause on same button
  if (currentPreviewBtn === btn) {
    if (cardAudio.paused) {
      cardAudio.play().then(() => { btn.textContent = "⏸"; btn.classList.add("playing"); }).catch(() => {});
    } else {
      cardAudio.pause();
      btn.textContent = "▶";
      btn.classList.remove("playing");
    }
    return;
  }

  // Stop any other playing track
  cardAudio.pause();
  if (currentPreviewBtn) { currentPreviewBtn.textContent = "▶"; currentPreviewBtn.classList.remove("playing"); }
  currentPreviewBtn = null;

  const key = `${artist} - ${song}`;
  const cached = musicUrlCache[key];

  if (cached === undefined || cached === "loading") {
    btn.textContent = "…";
    currentPreviewBtn = btn;
    const poll = setInterval(() => {
      const v = musicUrlCache[key];
      if (v === undefined || v === "loading") return;
      clearInterval(poll);
      if (currentPreviewBtn !== btn) return;
      if (!v) { btn.textContent = "▶"; currentPreviewBtn = null; return; }
      btn.textContent = "▶";
      handlePreview(btn, artist, song);
    }, 150);
    return;
  }

  if (!cached) {
    btn.textContent = "—";
    setTimeout(() => btn.textContent = "▶", 2000);
    return;
  }

  currentPreviewBtn = btn;
  cardAudio.src = cached;
  cardAudio.currentTime = 0;
  cardAudio.onended = () => {
    btn.textContent = "▶";
    btn.classList.remove("playing");
    if (currentPreviewBtn === btn) currentPreviewBtn = null;
  };
  cardAudio.play().then(() => {
    btn.textContent = "⏸";
    btn.classList.add("playing");
  }).catch(() => {
    btn.textContent = "▶";
    btn.classList.remove("playing");
    currentPreviewBtn = null;
  });
}

// ── Music → Preview integration ──

function fmtTime(sec) {
  const s = Math.floor(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function addMusicToPreview(cardEl, artist, song) {
  playSound("caption-select");

  // Stop anything currently playing
  cardAudio.pause();
  if (currentPreviewBtn) { currentPreviewBtn.textContent = "▶"; currentPreviewBtn.classList.remove("playing"); currentPreviewBtn = null; }
  trimAudio.pause();

  // Highlight selected card
  if (selectedMusicCardEl) selectedMusicCardEl.classList.remove("preview-selected");
  selectedMusicCardEl = cardEl;
  cardEl.classList.add("preview-selected");

  // Show music bar overlay
  const scrollText = document.getElementById("ig-music-scroll-text");
  if (scrollText) scrollText.textContent = `${artist} — ${song}`;
  document.getElementById("ig-music-bar")?.classList.remove("hidden");

  // Show trim panel in loading state
  const mtp = document.getElementById("mtp");
  document.getElementById("mtp-info").textContent = `${artist} — ${song}`;
  document.getElementById("mtp-start").value = 0;
  document.getElementById("mtp-length").value = 30;
  document.getElementById("mtp-start-val").textContent = "0:00";
  document.getElementById("mtp-length-val").textContent = "0:30";
  document.getElementById("mtp-start").max = 27; // 30 - min clip 3s
  mtp.classList.remove("hidden");
  updateMtpPlayBtn("loading");

  // Use cached URL (pre-fetched when music rendered) — no await needed
  previewMusicTrack = { artist, song };
  const key = `${artist} - ${song}`;
  const cached = musicUrlCache[key];
  previewMusicUrl = (cached && cached !== "loading") ? cached : null;

  if (previewMusicUrl) {
    updateMtpPlayBtn("stopped");
  } else if (!cached || cached === "loading") {
    updateMtpPlayBtn("loading");
    prefetchMusicUrls([{ artist, song }]).then(() => {
      previewMusicUrl = musicUrlCache[key] || null;
      updateMtpPlayBtn(previewMusicUrl ? "stopped" : "unavailable");
    });
  } else {
    updateMtpPlayBtn("unavailable");
  }
}

function updateMtpPlayBtn(state) {
  const btn = document.getElementById("mtp-play");
  if (!btn) return;
  btn.classList.remove("playing");
  if (state === "playing")      { btn.textContent = "⏸"; btn.classList.add("playing"); }
  else if (state === "loading") { btn.textContent = "…"; btn.disabled = true; }
  else if (state === "unavailable") { btn.textContent = "—"; btn.disabled = true; }
  else                          { btn.textContent = "▶"; btn.disabled = false; }
}

let mtpStopTimer = null;

// Trim panel — play/pause
document.getElementById("mtp-play").addEventListener("click", () => {
  if (!previewMusicUrl) return;

  if (!trimAudio.paused) {
    trimAudio.pause();
    clearTimeout(mtpStopTimer);
    updateMtpPlayBtn("stopped");
    return;
  }

  const startSec = parseFloat(document.getElementById("mtp-start").value);
  const lengthSec = parseFloat(document.getElementById("mtp-length").value);

  // Reuse pre-unlocked trimAudio — set src and play synchronously
  trimAudio.src = previewMusicUrl;
  trimAudio.currentTime = startSec;
  trimAudio.onended = () => updateMtpPlayBtn("stopped");

  trimAudio.play().then(() => {
    updateMtpPlayBtn("playing");
    clearTimeout(mtpStopTimer);
    mtpStopTimer = setTimeout(() => {
      if (!trimAudio.paused) { trimAudio.pause(); updateMtpPlayBtn("stopped"); }
    }, lengthSec * 1000);
  }).catch(() => updateMtpPlayBtn("stopped"));
});

// Start slider — cap length so start + length ≤ 30
document.getElementById("mtp-start").addEventListener("input", e => {
  const startSec = parseFloat(e.target.value);
  document.getElementById("mtp-start-val").textContent = fmtTime(startSec);
  const lengthEl = document.getElementById("mtp-length");
  const maxLen = Math.max(3, 30 - startSec);
  lengthEl.max = maxLen;
  if (parseFloat(lengthEl.value) > maxLen) {
    lengthEl.value = maxLen;
    document.getElementById("mtp-length-val").textContent = fmtTime(maxLen);
  }
  if (!trimAudio.paused) trimAudio.currentTime = startSec;
});

// Length slider — cap start so start + length ≤ 30
document.getElementById("mtp-length").addEventListener("input", e => {
  const lengthSec = parseFloat(e.target.value);
  document.getElementById("mtp-length-val").textContent = fmtTime(lengthSec);
  const startEl = document.getElementById("mtp-start");
  const maxStart = Math.max(0, 30 - lengthSec);
  startEl.max = maxStart;
  if (parseFloat(startEl.value) > maxStart) {
    startEl.value = maxStart;
    document.getElementById("mtp-start-val").textContent = fmtTime(maxStart);
    if (!trimAudio.paused) trimAudio.currentTime = maxStart;
  }
});

// Remove music from preview
document.getElementById("mtp-remove").addEventListener("click", () => {
  trimAudio.pause();
  trimAudio.src = "";
  clearTimeout(mtpStopTimer);
  previewMusicUrl = null;
  previewMusicTrack = null;
  if (selectedMusicCardEl) { selectedMusicCardEl.classList.remove("preview-selected"); selectedMusicCardEl = null; }
  document.getElementById("ig-music-bar")?.classList.add("hidden");
  document.getElementById("mtp").classList.add("hidden");
  const btn = document.getElementById("mtp-play");
  if (btn) { btn.textContent = "▶"; btn.disabled = false; btn.classList.remove("playing"); }
});

// Custom song input
document.getElementById("btn-add-song").addEventListener("click", () => {
  const input = document.getElementById("custom-song-input");
  const val = input.value.trim();
  if (!val) return;

  const parts = val.split(/\s*[—–-]\s*/);
  const artist = parts.length >= 2 ? parts[0].trim() : "Custom";
  const song = parts.length >= 2 ? parts.slice(1).join(" - ").trim() : val;

  currentMusicItems.push({ artist, song });
  _drawMusicList();
  input.value = "";
  playSound("caption-select");
});

document.getElementById("custom-song-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("btn-add-song").click();
});

function renderCaptions(captions) {
  captionList.innerHTML = "";
  selectedWrap.classList.add("hidden");

  // Preload image in preview immediately
  const preview = document.getElementById("post-preview");
  const mediaImg = document.getElementById("ig-media-img");
  const badge = document.getElementById("ig-carousel-badge");
  const capText = document.getElementById("ig-cap-text");
  if (selectedFiles.length) {
    mediaImg.src = URL.createObjectURL(selectedFiles[0]);
    if (selectedFiles.length > 1) {
      badge.textContent = `1 / ${selectedFiles.length}`;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }
  capText.textContent = "";
  preview.classList.remove("hidden");

  // Prefetch all music sets in background
  const allTracks = Object.values(allMusic).flat();
  prefetchMusicUrls(allTracks);

  const cards = [];
  captions.forEach((text, i) => {
    const card = document.createElement("div");
    card.className = "caption-card";
    card.innerHTML = `
      <div class="caption-badge">${CAPTION_LABELS[i] || `Option ${i + 1}`}</div>
      <div class="caption-text">${text}</div>
    `;
    card.addEventListener("click", () => selectCaption(card, text, i));
    captionList.appendChild(card);
    cards.push({ card, text, i });
    setTimeout(() => card.classList.add("visible"), i * 120);
  });

  // Auto-select first caption after cards animate in
  if (cards.length) {
    setTimeout(() => selectCaption(cards[0].card, cards[0].text, 0, true), 420);
  }
}

function selectCaption(card, text, index, silent = false) {
  if (!silent) {
    playSound("caption-select");
    track("caption_select", { index });
  }
  document.querySelectorAll(".caption-card").forEach(c => c.classList.remove("selected"));
  card.classList.add("selected");
  selectedCaption = text;
  captionEdit.value = text;
  document.getElementById("ig-cap-text").textContent = " " + text;
  selectedWrap.classList.remove("hidden");

  // Swap music to the set for this caption
  const key = String(index + 1);
  renderMusic(allMusic[key] || []);

  if (!silent) {
    document.getElementById("post-preview").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function updatePostPreview(text) {
  const preview = document.getElementById("post-preview");
  const mediaImg = document.getElementById("ig-media-img");
  const capText = document.getElementById("ig-cap-text");
  const badge = document.getElementById("ig-carousel-badge");

  if (selectedFiles.length) {
    mediaImg.src = URL.createObjectURL(selectedFiles[0]);
    if (selectedFiles.length > 1) {
      badge.textContent = `1 / ${selectedFiles.length}`;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }

  capText.textContent = " " + text;
  preview.classList.remove("hidden");
}

captionEdit.addEventListener("input", () => {
  selectedCaption = captionEdit.value;
  const capText = document.getElementById("ig-cap-text");
  if (capText) capText.textContent = " " + captionEdit.value;
});

function openInstagram() {
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  if (isMobile) {
    window.location.href = "instagram://";
    setTimeout(() => window.open("https://www.instagram.com", "_blank"), 900);
  } else {
    window.open("https://www.instagram.com", "_blank");
  }
}

// Post — copies caption and opens Instagram
btnPost.addEventListener("click", async () => {
  const caption = captionEdit.value.trim();
  if (!caption) return;

  // Copy caption to clipboard first
  try {
    await navigator.clipboard.writeText(caption);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = caption;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  playSound("success");
  showScreen("screen-success");
  launchConfetti();
  track("post_open");
  openInstagram();
});

// Back button
btnBack.addEventListener("click", () => {
  clearFiles();
  showScreen("screen-upload");
});

// New post
btnNew.addEventListener("click", () => {
  clearFiles();
  selectedCaption = "";
  captionEdit.value = "";
  captionList.innerHTML = "";
  selectedWrap.classList.add("hidden");
  document.getElementById("post-preview").classList.add("hidden");
  document.getElementById("ig-music-bar")?.classList.add("hidden");
  document.getElementById("mtp").classList.add("hidden");
  trimAudio.pause(); trimAudio.src = "";
  if (selectedMusicCardEl) { selectedMusicCardEl.classList.remove("preview-selected"); selectedMusicCardEl = null; }
  previewMusicUrl = null;
  showScreen("screen-upload");
});

// ── Draft management ──
function getDrafts() {
  try { return JSON.parse(localStorage.getItem("captionly_drafts") || "[]"); } catch { return []; }
}
function saveDrafts(drafts) {
  localStorage.setItem("captionly_drafts", JSON.stringify(drafts));
}

async function saveCurrentDraft() {
  const caption = captionEdit.value.trim();
  if (!caption) return;

  let imageThumb = "";
  if (selectedFiles.length) {
    try {
      imageThumb = await fileToThumb(selectedFiles[0]);
    } catch {}
  }

  const draft = {
    id: Date.now().toString(),
    caption,
    imageThumb,
    tones: Array.from(selectedTones),
    genres: Array.from(selectedGenres),
    status: "draft",
    createdAt: new Date().toISOString(),
    scheduledFor: null,
    notes: "",
  };

  const drafts = getDrafts();
  drafts.unshift(draft);
  saveDrafts(drafts);

  const btn = document.getElementById("btn-save-draft");
  const orig = btn.textContent;
  btn.textContent = "✓ Saved";
  setTimeout(() => btn.textContent = orig, 2000);
  playSound("success");
  track("draft_save");
}

async function fileToThumb(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = e => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const size = 80;
        canvas.width = size; canvas.height = size;
        const ctx = canvas.getContext("2d");
        const ratio = Math.max(size / img.width, size / img.height);
        const w = img.width * ratio, h = img.height * ratio;
        ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.6));
      };
      img.onerror = reject;
      img.src = e.target.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const STATUS_CYCLE = ["draft", "ready", "scheduled", "posted"];
const STATUS_LABELS = { draft: "Draft", ready: "Ready", scheduled: "Scheduled", posted: "Posted" };

function renderDrafts() {
  const drafts = getDrafts();
  const listEl = document.getElementById("drafts-list");
  const emptyEl = document.getElementById("drafts-empty");
  listEl.innerHTML = "";

  if (!drafts.length) {
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");

  drafts.forEach(draft => {
    const card = document.createElement("div");
    card.className = "draft-card";
    const date = new Date(draft.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const snippet = draft.caption.slice(0, 80) + (draft.caption.length > 80 ? "…" : "");

    const schedLabel = draft.scheduledFor
      ? "📅 " + new Date(draft.scheduledFor + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })
      : "📅";
    const schedClass = draft.scheduledFor ? " is-scheduled" : "";

    card.innerHTML = `
      <div class="draft-thumb">
        ${draft.imageThumb ? `<img src="${draft.imageThumb}" alt="" />` : '<div class="draft-thumb-placeholder">📷</div>'}
      </div>
      <div class="draft-info">
        <div class="draft-caption">${snippet}</div>
        <div class="draft-meta">
          <span class="draft-date">${date}</span>
          <button class="draft-status status-${draft.status}" data-id="${draft.id}">${STATUS_LABELS[draft.status]}</button>
          <button class="draft-schedule-btn${schedClass}" data-id="${draft.id}" title="Pin to calendar date">${schedLabel}</button>
          <input type="date" class="draft-date-input" data-id="${draft.id}" style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none" ${draft.scheduledFor ? `value="${draft.scheduledFor}"` : ""} />
        </div>
      </div>
      <button class="draft-delete" data-id="${draft.id}">✕</button>
    `;

    card.querySelector(".draft-info").addEventListener("click", () => loadDraft(draft));

    card.querySelector(".draft-status").addEventListener("click", e => {
      e.stopPropagation();
      cycleDraftStatus(draft.id);
      playSound("click");
    });

    const schedBtn = card.querySelector(".draft-schedule-btn");
    const dateInput = card.querySelector(".draft-date-input");
    schedBtn.addEventListener("click", e => {
      e.stopPropagation();
      dateInput.click();
    });
    dateInput.addEventListener("change", e => {
      e.stopPropagation();
      scheduleDraft(draft.id, e.target.value || null);
    });

    card.querySelector(".draft-delete").addEventListener("click", e => {
      e.stopPropagation();
      deleteDraft(draft.id);
      playSound("click");
    });

    listEl.appendChild(card);
  });
}

function cycleDraftStatus(id) {
  const drafts = getDrafts();
  const d = drafts.find(x => x.id === id);
  if (!d) return;
  const idx = STATUS_CYCLE.indexOf(d.status);
  d.status = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
  saveDrafts(drafts);
  renderDrafts();
}

function deleteDraft(id) {
  const drafts = getDrafts().filter(x => x.id !== id);
  saveDrafts(drafts);
  renderDrafts();
}

function loadDraft(draft) {
  captionEdit.value = draft.caption;
  selectedCaption = draft.caption;
  document.getElementById("ig-cap-text").textContent = " " + draft.caption;
  selectedWrap.classList.remove("hidden");
  showScreen("screen-captions");
}

document.getElementById("btn-save-draft").addEventListener("click", saveCurrentDraft);

// ── Calendar ──
let calYear = new Date().getFullYear();
let calMonth = new Date().getMonth();
const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

function renderCalendar() {
  const labelEl = document.getElementById("calendar-month-label");
  const gridEl = document.getElementById("calendar-grid");
  if (!labelEl || !gridEl) return;

  labelEl.textContent = `${MONTH_NAMES[calMonth]} ${calYear}`;
  gridEl.innerHTML = "";

  const drafts = getDrafts();
  const draftDates = new Set();
  drafts.forEach(d => {
    if (d.scheduledFor) draftDates.add(d.scheduledFor.slice(0, 10));
    if (d.createdAt) draftDates.add(d.createdAt.slice(0, 10));
  });

  const today = new Date();
  const firstDay = new Date(calYear, calMonth, 1).getDay();
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

  ["Su","Mo","Tu","We","Th","Fr","Sa"].forEach(d => {
    const el = document.createElement("div");
    el.className = "cal-day-header";
    el.textContent = d;
    gridEl.appendChild(el);
  });

  for (let i = 0; i < firstDay; i++) {
    const el = document.createElement("div");
    el.className = "cal-day empty";
    gridEl.appendChild(el);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${calYear}-${String(calMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const isToday = today.getFullYear() === calYear && today.getMonth() === calMonth && today.getDate() === d;
    const hasDraft = draftDates.has(dateStr);

    const el = document.createElement("div");
    el.className = "cal-day" + (isToday ? " today" : "") + (hasDraft ? " has-draft" : "");
    el.innerHTML = `<span class="cal-day-num">${d}</span>${hasDraft ? '<span class="cal-dot"></span>' : ""}`;
    if (hasDraft) {
      el.addEventListener("click", () => showDayDetail(dateStr));
    }
    gridEl.appendChild(el);
  }
}

document.getElementById("cal-prev")?.addEventListener("click", () => {
  calMonth--;
  if (calMonth < 0) { calMonth = 11; calYear--; }
  renderCalendar();
  playSound("click");
});

document.getElementById("cal-next")?.addEventListener("click", () => {
  calMonth++;
  if (calMonth > 11) { calMonth = 0; calYear++; }
  renderCalendar();
  playSound("click");
});

// --- Settings ---

const btnSaveCaptions = document.getElementById("btn-save-captions");
const manualCaptions  = document.getElementById("manual-captions");
const manualStatus    = document.getElementById("manual-status");
const setupConnect    = document.getElementById("setup-connect");
const setupConnected  = document.getElementById("setup-connected");
const connectedName   = document.getElementById("connected-name");

// Set Instagram login URL
document.getElementById("btn-instagram-login").href = `${API_URL}/auth/instagram`;

// Check for auth callback params on load
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get("auth") === "success") {
  const username = urlParams.get("username");
  showConnected(username);
  history.replaceState({}, "", window.location.pathname);
} else if (urlParams.get("auth") === "error") {
  alert("Instagram connection failed. Please try again.");
  history.replaceState({}, "", window.location.pathname);
}

function showConnected(username) {
  setupConnect.classList.add("hidden");
  setupConnected.classList.remove("hidden");
  connectedName.textContent = username ? `@${username}` : "Instagram connected";
}

function showDisconnected() {
  setupConnected.classList.add("hidden");
  setupConnect.classList.remove("hidden");
}

async function loadSettingsData() {
  try {
    const res = await fetch(`${API_URL}/settings/captions`);
    const data = await res.json();
    if (data.captions?.length) manualCaptions.value = data.captions.join("\n");
  } catch {}
  try {
    const res = await fetch(`${API_URL}/auth/status`);
    const data = await res.json();
    if (data.connected) {
      document.getElementById("setup-connect").classList.add("hidden");
      document.getElementById("setup-connected").classList.remove("hidden");
      document.getElementById("connected-name").textContent = `@${data.username}`;
    } else {
      document.getElementById("setup-connect").classList.remove("hidden");
      document.getElementById("setup-connected").classList.add("hidden");
    }
  } catch {}
}

document.getElementById("btn-disconnect").addEventListener("click", async () => {
  await fetch(`${API_URL}/auth/logout`, { method: "POST" });
  document.getElementById("user-pill").classList.add("hidden");
  document.getElementById("setup-connect").classList.remove("hidden");
  document.getElementById("setup-connected").classList.add("hidden");
  setActiveTab("create");
  showScreen("screen-upload");
});

// Save manually pasted captions
btnSaveCaptions.addEventListener("click", async () => {
  const lines = manualCaptions.value.split("\n").map(l => l.trim()).filter(Boolean);
  if (!lines.length) return alert("Paste at least one caption");

  const res = await fetch(`${API_URL}/settings/captions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ captions: lines }),
  });

  if (res.ok) {
    showStatus(manualStatus, `${lines.length} captions saved — Claude will match this voice`);
  } else {
    showStatus(manualStatus, "Failed to save");
  }
});

function showStatus(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 5000);
}

// ── Schedule draft to a calendar date ──
function scheduleDraft(id, dateStr) {
  const drafts = getDrafts();
  const d = drafts.find(x => x.id === id);
  if (!d) return;
  d.scheduledFor = dateStr || null;
  saveDrafts(drafts);
  renderDrafts();
  renderCalendar();
  track("draft_schedule", { date: dateStr || "removed" });
}

// ── Day detail bottom sheet ──
function showDayDetail(dateStr) {
  const overlay = document.getElementById("day-detail-overlay");
  const dateEl = document.getElementById("day-detail-date");
  const listEl = document.getElementById("day-detail-list");

  const d = new Date(dateStr + "T00:00:00");
  dateEl.textContent = d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  const allDrafts = getDrafts();
  const dayDrafts = allDrafts.filter(draft =>
    (draft.scheduledFor && draft.scheduledFor.slice(0, 10) === dateStr) ||
    (draft.createdAt && draft.createdAt.slice(0, 10) === dateStr)
  );

  listEl.innerHTML = "";
  if (!dayDrafts.length) {
    listEl.innerHTML = '<div class="day-detail-empty">No drafts found for this date.</div>';
  } else {
    dayDrafts.forEach(draft => {
      const item = document.createElement("div");
      item.className = "draft-card";
      const snippet = draft.caption.slice(0, 100) + (draft.caption.length > 100 ? "…" : "");
      item.innerHTML = `
        <div class="draft-thumb">
          ${draft.imageThumb ? `<img src="${draft.imageThumb}" alt="" />` : '<div class="draft-thumb-placeholder">📷</div>'}
        </div>
        <div class="draft-info">
          <div class="draft-caption">${snippet}</div>
          <div class="draft-meta">
            <span class="draft-status status-${draft.status}">${STATUS_LABELS[draft.status]}</span>
          </div>
        </div>
        <button class="day-detail-open-btn">Open →</button>
      `;
      item.querySelector(".day-detail-open-btn").addEventListener("click", () => {
        closeDayDetail();
        setTimeout(() => {
          loadDraft(draft);
          setActiveTab("create");
        }, 300);
        track("day_detail_open_draft");
      });
      listEl.appendChild(item);
    });
  }

  overlay.classList.remove("hidden");
  playSound("swipe");
  track("day_detail_open", { date: dateStr, count: dayDrafts.length });
}

function closeDayDetail() {
  document.getElementById("day-detail-overlay").classList.add("hidden");
}

document.getElementById("day-detail-close").addEventListener("click", closeDayDetail);
document.getElementById("day-detail-backdrop").addEventListener("click", closeDayDetail);

// ── Theme switcher ──
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme === "rose" ? "" : theme);
  localStorage.setItem("cap_theme", theme);
  document.querySelectorAll(".theme-swatch").forEach(s =>
    s.classList.toggle("active", s.dataset.theme === theme)
  );
  track("theme_change", { theme });
}

const savedTheme = localStorage.getItem("cap_theme") || "rose";
applyTheme(savedTheme);

document.querySelectorAll(".theme-swatch").forEach(swatch => {
  swatch.addEventListener("click", () => {
    applyTheme(swatch.dataset.theme);
    playSound("click");
  });
});
