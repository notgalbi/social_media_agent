const API_URL = "https://socialmediaagent-production-83c2.up.railway.app";

const CAPTION_LABELS = ["Casual", "Engaging", "Call to Action"];

let selectedFile = null;
let selectedCaption = "";

// Keep backend warm — ping every 4 minutes to prevent cold starts
setInterval(() => fetch(`${API_URL}/health`).catch(() => {}), 240000);

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
const previewImg = document.getElementById("preview-img");
const previewVideo = document.getElementById("preview-video");
const btnClear = document.getElementById("btn-clear");
const btnGenerate = document.getElementById("btn-generate");
const captionList = document.getElementById("caption-list");
const captionEdit = document.getElementById("caption-edit");
const selectedWrap = document.getElementById("selected-wrap");
const btnPost = document.getElementById("btn-post");
const btnBack = document.getElementById("btn-back");
const btnNew = document.getElementById("btn-new");

// Screens
function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}

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
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

function handleFile(file) {
  selectedFile = file;
  const url = URL.createObjectURL(file);
  const isVideo = file.type.startsWith("video/");

  if (isVideo) {
    previewVideo.src = url;
    previewVideo.classList.add("active");
    previewImg.classList.remove("active");
  } else {
    previewImg.src = url;
    previewImg.classList.add("active");
    previewVideo.classList.remove("active");
  }

  uploadArea.classList.add("hidden");
  previewWrap.classList.remove("hidden");
  btnGenerate.disabled = false;
}

btnClear.addEventListener("click", () => {
  selectedFile = null;
  previewImg.src = "";
  previewVideo.src = "";
  previewImg.classList.remove("active");
  previewVideo.classList.remove("active");
  previewWrap.classList.add("hidden");
  uploadArea.classList.remove("hidden");
  btnGenerate.disabled = true;
  fileInput.value = "";
});

// Generate captions
btnGenerate.addEventListener("click", async () => {
  if (!selectedFile) return;

  showScreen("screen-loading");

  const formData = new FormData();
  formData.append("file", selectedFile);

  const loaderText = document.getElementById("loader-text");
  const messages = ["Reading your dish...", "Analyzing the photo...", "Writing captions..."];
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

    if (!res.ok) throw new Error("Failed to generate captions");

    const data = await res.json();
    clearInterval(msgInterval);
    renderCaptions(data.captions);
    renderMusic(data.music || []);
    showScreen("screen-captions");
  } catch (err) {
    clearInterval(msgInterval);
    const msg = err.name === "AbortError"
      ? "Taking too long — try a smaller photo or video."
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
  });
}

function selectCaption(card, text) {
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

      showScreen("screen-success");
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
  }
});

// Back button
btnBack.addEventListener("click", () => {
  showScreen("screen-upload");
  btnClear.click();
});

// New post
btnNew.addEventListener("click", () => {
  selectedFile = null;
  selectedCaption = "";
  captionEdit.value = "";
  captionList.innerHTML = "";
  selectedWrap.classList.add("hidden");
  previewWrap.classList.add("hidden");
  uploadArea.classList.remove("hidden");
  btnGenerate.disabled = true;
  fileInput.value = "";
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

  // load captions into textarea
  try {
    const res = await fetch(`${API_URL}/settings/captions`);
    const data = await res.json();
    if (data.captions?.length) manualCaptions.value = data.captions.join("\n");
  } catch {}

  // check Instagram connection status
  try {
    const res = await fetch(`${API_URL}/auth/status`);
    const data = await res.json();
    if (data.connected) {
      showConnected(data.username);
    } else {
      showDisconnected();
    }
  } catch {
    showDisconnected();
  }
});

btnSettingsBack.addEventListener("click", () => showScreen("screen-upload"));

document.getElementById("btn-disconnect").addEventListener("click", async () => {
  await fetch(`${API_URL}/auth/logout`, { method: "POST" });
  showDisconnected();
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
