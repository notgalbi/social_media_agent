const API_URL = "http://localhost:8000";

const CAPTION_LABELS = ["Casual", "Engaging", "Call to Action"];

let selectedFile = null;
let selectedCaption = "";

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

  try {
    const res = await fetch(`${API_URL}/generate-captions`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error("Failed to generate captions");

    const data = await res.json();
    renderCaptions(data.captions);
    showScreen("screen-captions");
  } catch (err) {
    alert("Something went wrong. Make sure the backend is running.");
    showScreen("screen-upload");
  }
});

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

// Step elements
const igToken         = document.getElementById("ig-token");
const step1           = document.getElementById("setup-step-1");
const step2           = document.getElementById("setup-step-2");
const step3           = document.getElementById("setup-step-3");
const setupConnected  = document.getElementById("setup-connected");
const profileList     = document.getElementById("profile-list");
const connectedName   = document.getElementById("connected-name");

let pendingToken = "";

function setStep(n) {
  [step1, step2, step3, setupConnected].forEach(el => el.classList.add("hidden"));
  [1,2,3].forEach(i => {
    const dot = document.getElementById(`step-dot-${i}`);
    dot.classList.toggle("active", i === n);
    dot.classList.toggle("done", i < n);
  });
  if (n === "connected") {
    setupConnected.classList.remove("hidden");
    document.getElementById("setup-steps").classList.add("hidden");
  } else {
    document.getElementById("setup-steps").classList.remove("hidden");
    document.getElementById(`setup-step-${n}`).classList.remove("hidden");
  }
}

btnSettings.addEventListener("click", async () => {
  showScreen("screen-settings");

  // load captions
  try {
    const res = await fetch(`${API_URL}/settings/captions`);
    const data = await res.json();
    if (data.captions?.length) manualCaptions.value = data.captions.join("\n");
  } catch {}

  // check if already connected
  try {
    const res = await fetch(`${API_URL}/settings/buffer`);
    const data = await res.json();
    if (data.connected) {
      connectedName.textContent = data.username || "Instagram connected";
      setStep("connected");
      return;
    }
  } catch {}

  setStep(1);
});

btnSettingsBack.addEventListener("click", () => showScreen("screen-upload"));

// Step 1: token input → enable next
igToken.addEventListener("input", () => {
  document.getElementById("btn-step1-next").disabled = igToken.value.trim().length < 10;
});

document.getElementById("btn-step1-next").addEventListener("click", () => {
  pendingToken = igToken.value.trim();
  setStep(2);
});

document.getElementById("btn-step2-next").addEventListener("click", () => setStep(3));
document.getElementById("btn-step2-back").addEventListener("click", () => setStep(1));
document.getElementById("btn-step3-back").addEventListener("click", () => setStep(2));

// Step 3: fetch Instagram profiles from Buffer
document.getElementById("btn-fetch-profiles").addEventListener("click", async () => {
  showStatus(syncStatus, "Fetching profiles...");
  try {
    const res = await fetch(`${API_URL}/settings/buffer/profiles?access_token=${encodeURIComponent(pendingToken)}`);
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || "Could not fetch profiles");
    if (!data.profiles.length) throw new Error("No Instagram accounts found in Buffer. Connect one first.");

    profileList.innerHTML = "";
    data.profiles.forEach(p => {
      const btn = document.createElement("button");
      btn.className = "btn-profile";
      btn.textContent = `@${p.name}`;
      btn.addEventListener("click", () => saveBuffer(p.id, p.name));
      profileList.appendChild(btn);
    });

    profileList.classList.remove("hidden");
    syncStatus.classList.add("hidden");
  } catch (err) {
    showStatus(syncStatus, err.message);
  }
});

async function saveBuffer(profileId, username) {
  const res = await fetch(`${API_URL}/settings/buffer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: pendingToken, profile_id: profileId }),
  });
  if (res.ok) {
    connectedName.textContent = `@${username}`;
    setStep("connected");
  } else {
    showStatus(syncStatus, "Failed to save — try again");
  }
}

document.getElementById("btn-disconnect").addEventListener("click", async () => {
  await fetch(`${API_URL}/settings/buffer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: "", profile_id: "" }),
  });
  igToken.value = "";
  pendingToken = "";
  setStep(1);
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
