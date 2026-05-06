const API_URL = "https://socialmediaagent-production-83c2.up.railway.app";

// ── Sound system (Web Audio API — no files needed) ──
let audioCtx = null;

function getAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

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

// ── Particle background ──
function spawnParticles() {
  const container = document.getElementById("particles");
  const colors = ["#f7c5d2", "#e8b97a", "#c8e6c8", "#f0dde5", "#fde8ed"];
  for (let i = 0; i < 18; i++) {
    const p = document.createElement("div");
    p.className = "particle";
    const size = Math.random() * 10 + 4;
    p.style.cssText = `
      width: ${size}px; height: ${size}px;
      left: ${Math.random() * 100}%;
      background: ${colors[Math.floor(Math.random() * colors.length)]};
      animation-duration: ${Math.random() * 12 + 10}s;
      animation-delay: ${Math.random() * 10}s;
    `;
    container.appendChild(p);
  }
}
spawnParticles();

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
}

const CAPTION_LABELS = ["Casual", "Engaging", "Call to Action"];

let selectedFiles = [];
let selectedCaption = "";

// Keep backend warm
setInterval(() => fetch(`${API_URL}/health`).catch(() => {}), 240000);

// Set login URL
document.getElementById("btn-instagram-login").href = `${API_URL}/auth/instagram`;

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

function enterApp(username) {
  document.getElementById("main-header").classList.remove("hidden");
  const pill = document.getElementById("user-pill");
  const connectedName = document.getElementById("connected-name");

  if (username) {
    pill.textContent = `⚡ @${username}`;
    pill.classList.remove("hidden");
    connectedName.textContent = `@${username}`;
    // show connected state in settings
    document.getElementById("setup-connect").classList.add("hidden");
    document.getElementById("setup-connected").classList.remove("hidden");
  }

  showScreen("screen-upload");
}

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
  if (selectedFiles.length) playSound("upload");
}

function renderCarousel() {
  const strip = document.getElementById("carousel-strip");
  const countEl = document.getElementById("carousel-count");
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

// Generate captions
btnGenerate.addEventListener("click", async () => {
  if (!selectedFiles.length) return;

  playSound("generate");
  showScreen("screen-loading");

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append("files", f));

  const loaderText = document.getElementById("loader-text");
  const isCarousel = selectedFiles.length > 1;
  const messages = [
    "Reading your content...",
    isCarousel ? `Analyzing ${selectedFiles.length} photos...` : "Analyzing the photo...",
    "Writing captions...",
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
    renderCaptions(data.captions);
    renderMusic(data.music || []);
    showScreen("screen-captions");
  } catch (err) {
    clearInterval(msgInterval);
    const msg = err.name === "AbortError"
      ? "Taking too long — try a smaller photo or video."
      : err.message.startsWith("Server error") || err.message.length < 120
        ? err.message
        : "Could not reach the server. Check your connection and try again.";
    alert(msg);
    showScreen("screen-upload");
  }
});

function renderMusic(music) {
  const wrap = document.getElementById("music-wrap");
  const list = document.getElementById("music-list");
  list.innerHTML = "";

  if (!music || !music.length) {
    wrap.classList.add("hidden");
    return;
  }

  music.forEach((track, i) => {
    const el = document.createElement("div");
    el.className = "music-card";
    el.innerHTML = `
      <div class="music-num">${i + 1}</div>
      <div class="music-info">
        <div class="music-song">${track.song}</div>
        <div class="music-artist">${track.artist}</div>
      </div>
      <button class="music-copy" title="Copy song name" data-text="${track.artist} - ${track.song}">⎘</button>
    `;
    el.querySelector(".music-copy").addEventListener("click", async (e) => {
      playSound("music-copy");
      const text = e.currentTarget.dataset.text;
      try { await navigator.clipboard.writeText(text); } catch {}
      e.currentTarget.textContent = "✓";
      setTimeout(() => e.currentTarget.textContent = "⎘", 2000);
    });
    list.appendChild(el);
  });

  wrap.classList.remove("hidden");
}

function renderCaptions(captions) {
  captionList.innerHTML = "";
  selectedWrap.classList.add("hidden");

  captions.forEach((text, i) => {
    const card = document.createElement("div");
    card.className = "caption-card";
    card.innerHTML = `
      <div class="caption-badge">${CAPTION_LABELS[i] || `Option ${i + 1}`}</div>
      <div class="caption-text">${text}</div>
    `;
    card.addEventListener("click", () => selectCaption(card, text));
    captionList.appendChild(card);
    // staggered entrance
    setTimeout(() => card.classList.add("visible"), i * 120);
  });
}

function selectCaption(card, text) {
  playSound("caption-select");
  document.querySelectorAll(".caption-card").forEach(c => c.classList.remove("selected"));
  card.classList.add("selected");
  selectedCaption = text;
  captionEdit.value = text;
  selectedWrap.classList.remove("hidden");
  selectedWrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

captionEdit.addEventListener("input", () => {
  selectedCaption = captionEdit.value;
});

// Post via Buffer or copy to clipboard
btnPost.addEventListener("click", async () => {
  const caption = captionEdit.value.trim();
  if (!caption) return;

  // check if Buffer is connected
  let bufferConnected = false;
  try {
    const check = await fetch(`${API_URL}/settings/buffer`);
    const data = await check.json();
    bufferConnected = data.connected;
  } catch {}

  if (bufferConnected && selectedFile) {
    btnPost.disabled = true;
    btnPost.textContent = "Posting...";
    try {
      // upload the media file first
      const formData = new FormData();
      formData.append("file", selectedFile);
      const uploadRes = await fetch(`${API_URL}/upload-media`, {
        method: "POST",
        body: formData,
      });
      const { filename } = await uploadRes.json();

      // post to Instagram via Buffer
      const postRes = await fetch(`${API_URL}/post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caption, image_filename: filename }),
      });

      if (!postRes.ok) {
        const err = await postRes.json();
        throw new Error(err.detail || "Post failed");
      }

      playSound("success");
      showScreen("screen-success");
      launchConfetti();
    } catch (err) {
      alert(`Could not post: ${err.message}`);
    } finally {
      btnPost.disabled = false;
      btnPost.textContent = "Post to Instagram";
    }
  } else {
    // fallback: copy to clipboard
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
    showScreen("screen-success");
    launchConfetti();
  }
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
  showScreen("screen-upload");
});

// --- Settings ---

const btnSettings     = document.getElementById("btn-settings");
const btnSettingsBack = document.getElementById("btn-settings-back");
const btnSaveCaptions = document.getElementById("btn-save-captions");
const manualCaptions  = document.getElementById("manual-captions");
const manualStatus    = document.getElementById("manual-status");
const syncStatus      = document.getElementById("sync-status");
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

btnSettings.addEventListener("click", async () => {
  showScreen("screen-settings");
  try {
    const res = await fetch(`${API_URL}/settings/captions`);
    const data = await res.json();
    if (data.captions?.length) manualCaptions.value = data.captions.join("\n");
  } catch {}

  // refresh connection status
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
});

btnSettingsBack.addEventListener("click", () => showScreen("screen-upload"));

document.getElementById("btn-disconnect").addEventListener("click", async () => {
  await fetch(`${API_URL}/auth/logout`, { method: "POST" });
  document.getElementById("user-pill").classList.add("hidden");
  document.getElementById("setup-connect").classList.remove("hidden");
  document.getElementById("setup-connected").classList.add("hidden");
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
