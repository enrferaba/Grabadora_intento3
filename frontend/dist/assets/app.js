const API_BASE = window.APP_API_BASE ?? "";
const STORAGE_KEY = "grabadora_auth";
const GUEST_QUOTA_MINUTES = 30;

const elements = {
  tabs: document.querySelectorAll(".tabs__item"),
  panels: document.querySelectorAll(".panel"),
  heroAuth: document.querySelector('[data-action="open-auth"]'),
  heroTranscribe: document.querySelectorAll('[data-action="open-transcribe"]'),
  signupForm: document.getElementById("signup-form"),
  loginForm: document.getElementById("login-form"),
  transcribeForm: document.getElementById("transcribe-form"),
  streamOutput: document.getElementById("stream-output"),
  streamStatus: document.getElementById("stream-status"),
  streamText: document.getElementById("stream-text"),
  uploadProgress: document.getElementById("upload-progress"),
  toast: document.getElementById("toast"),
  accountEmail: document.getElementById("account-email"),
  accountInitial: document.getElementById("account-initial"),
  metricMinutes: document.getElementById("metric-minutes"),
  metricQueue: document.getElementById("metric-queue"),
  metricSpeed: document.getElementById("metric-speed"),
  libraryList: document.getElementById("library-list"),
  libraryFilters: document.getElementById("library-filters"),
  meterBar: document.getElementById("meter-bar"),
  waveform: document.getElementById("waveform"),
  recordStart: document.querySelector('[data-action="start-recording"]'),
  recordStop: document.querySelector('[data-action="stop-recording"]'),
  recordUpload: document.querySelector('[data-action="upload-recording"]'),
  recordPreview: document.getElementById("recording-preview"),
  accountButton: document.querySelector('[data-action="toggle-account-menu"]'),
  accountMenu: document.getElementById("account-menu"),
  accountMenuItems: document.querySelectorAll("[data-menu-action]"),
};

const state = {
  token: null,
  email: null,
  streamController: null,
  activeJob: null,
  activeProfile: "balanced",
  transcripts: [],
  recorder: null,
  analyser: null,
  audioContext: null,
  animationFrame: null,
  recordedBlob: null,
  guest: false,
  recordedChunks: [],
};

function readStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed.token) {
      state.token = parsed.token;
      state.email = parsed.email ?? null;
      state.guest = Boolean(parsed.guest);
    }
  } catch (error) {
    console.warn("No se pudo leer el estado de autenticación", error);
  }
}

function persistAuth() {
  if (!state.token) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  const payload = {
    token: state.token,
    email: state.email,
    guest: state.guest,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function setAuth(token, email, { guest = false } = {}) {
  state.token = token;
  state.email = email;
  state.guest = guest;
  persistAuth();
  updateAccount();
  setAccountMenu(false);
  toggleAuthPanel(false);
  showToast(`Bienvenido${guest ? " (modo demo)" : ""}`);
  setActiveTab("transcribe");
  refreshLibrary();
}

function clearAuth() {
  state.token = null;
  state.email = null;
  state.guest = false;
  persistAuth();
  updateAccount();
  setAccountMenu(false);
  showToast("Sesión cerrada");
}

async function apiFetch(path, init = {}) {
  const headers = new Headers(init.headers || {});
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");
  if (state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const parsed = JSON.parse(detail);
      detail = parsed.detail || detail;
    } catch {
      // noop
    }
    throw new Error(detail || `Error ${response.status}`);
  }
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

async function signup(email, password) {
  await apiFetch("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  await login(email, password);
}

async function login(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  body.set("grant_type", "password");
  const response = await apiFetch("/auth/token", {
    method: "POST",
    body,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  setAuth(response.access_token, email, { guest: false });
}

async function startGuestSession() {
  const random = Math.random().toString(36).slice(2, 10);
  const email = `demo-${random}@guest.local`;
  const password = `Guest-${random}!`;
  try {
    await signup(email, password);
  } catch (error) {
    console.warn("No se pudo crear el invitado", error);
  }
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  body.set("grant_type", "password");
  const response = await apiFetch("/auth/token", {
    method: "POST",
    body,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  setAuth(response.access_token, email, { guest: true });
  showToast("Modo demo activo. Tus archivos se eliminan en 24h.");
}

function toggleAuthPanel(visible) {
  document.getElementById("panel-auth").hidden = !visible;
  if (visible) {
    document.getElementById("panel-auth").scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function isAccountMenuOpen() {
  return Boolean(elements.accountMenu) && !elements.accountMenu.hidden;
}

function setAccountMenu(open) {
  if (!elements.accountMenu || !elements.accountButton) return;
  elements.accountMenu.hidden = !open;
  elements.accountButton.setAttribute("aria-expanded", String(open));
}

function setActiveTab(tabId) {
  setAccountMenu(false);
  elements.tabs.forEach((tab) => {
    const match = tab.dataset.tab === tabId;
    tab.setAttribute("aria-selected", String(match));
  });
  elements.panels.forEach((panel) => {
    panel.hidden = panel.id !== `panel-${tabId}` && panel.id !== "panel-auth";
  });
  if (tabId === "library") {
    refreshLibrary();
  }
  if (tabId === "transcribe") {
    document.getElementById("panel-transcribe").hidden = false;
  }
  if (tabId === "record") {
    document.getElementById("panel-record").hidden = false;
  }
  if (tabId === "account") {
    document.getElementById("panel-account").hidden = false;
  }
}

function showToast(message, { tone = "info" } = {}) {
  elements.toast.textContent = message;
  elements.toast.dataset.tone = tone;
  elements.toast.dataset.visible = "true";
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => {
    elements.toast.dataset.visible = "false";
  }, 3500);
}

function resetStream() {
  if (state.streamController) {
    state.streamController.abort();
  }
  state.streamController = null;
  state.activeJob = null;
  elements.streamText.textContent = "";
  elements.streamStatus.textContent = "Esperando";
  elements.streamStatus.className = "chip";
  elements.streamOutput.hidden = true;
}

async function uploadAudio(formData, { onProgress } = {}) {
  return await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/transcribe`);
    if (state.token) {
      xhr.setRequestHeader("Authorization", `Bearer ${state.token}`);
    }
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(event.loaded / event.total);
      }
    };
    xhr.onerror = () => reject(new Error("No se pudo subir el audio"));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
      } else {
        const detail = xhr.response?.detail || xhr.statusText;
        reject(new Error(detail || "Error al subir"));
      }
    };
    xhr.send(formData);
  });
}

function updateProgress(value) {
  elements.uploadProgress.style.width = `${Math.min(100, Math.round(value * 100))}%`;
}

async function streamTranscription(jobId) {
  resetStream();
  elements.streamOutput.hidden = false;
  elements.streamStatus.textContent = "Procesando";
  elements.streamStatus.className = "chip chip--info";
  state.activeJob = jobId;
  const controller = new AbortController();
  state.streamController = controller;
  try {
    const response = await fetch(`${API_BASE}/transcribe/${jobId}`, {
      headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      throw new Error("No se pudo iniciar el stream");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        handleStreamEvent(event);
      }
    }
  } catch (error) {
    if (controller.signal.aborted) {
      elements.streamStatus.textContent = "Cancelado";
      elements.streamStatus.className = "chip";
    } else {
      console.error(error);
      elements.streamStatus.textContent = "Error";
      elements.streamStatus.className = "chip";
      showToast(error.message || "Error en el stream", { tone: "error" });
    }
  }
}

function handleStreamEvent(raw) {
  const lines = raw.split("\n");
  let type = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) {
      type = line.replace("event:", "").trim();
    } else if (line.startsWith("data:")) {
      data += `${line.replace("data:", "").trim()}\n`;
    }
  }
  const payloadText = data.trim();
  if (!payloadText) return;
  if (type === "delta") {
    try {
      const payload = JSON.parse(payloadText);
      if (payload.text) {
        elements.streamText.textContent += payload.text;
        elements.streamText.scrollTop = elements.streamText.scrollHeight;
      }
      updateMetrics({ profile: payload.quality_profile });
    } catch (error) {
      elements.streamText.textContent += payloadText;
    }
  } else if (type === "completed") {
    try {
      const payload = JSON.parse(payloadText);
      elements.streamStatus.textContent = "Completado";
      elements.streamStatus.className = "chip chip--success";
      showToast("Transcripción lista en tu biblioteca");
      refreshLibrary();
      if (payload.quality_profile) {
        updateMetrics({ profile: payload.quality_profile });
      }
    } catch (error) {
      elements.streamStatus.textContent = "Completado";
    }
  } else if (type === "error") {
    let detail = payloadText;
    try {
      const payload = JSON.parse(payloadText);
      detail = payload.detail || detail;
    } catch {
      // ignore
    }
    elements.streamStatus.textContent = "Error";
    elements.streamStatus.className = "chip";
    showToast(detail || "Fallo en la transcripción", { tone: "error" });
  }
}

function updateAccount() {
  if (elements.accountEmail) {
    elements.accountEmail.textContent = state.email ? `${state.email}${state.guest ? " (demo)" : ""}` : "Visitante";
  }
  if (elements.accountInitial) {
    const icon = state.email ? state.email.charAt(0).toUpperCase() : "👤";
    elements.accountInitial.textContent = state.guest ? "★" : icon;
  }
  if (elements.accountButton) {
    const label = state.email ? `Cuenta de ${state.email}` : "Opciones de cuenta";
    elements.accountButton.setAttribute("aria-label", label);
    elements.accountButton.setAttribute("title", label);
  }
}

function updateMetrics({ profile } = {}) {
  if (profile) {
    const labels = {
      fast: "Rápido (int8)",
      balanced: "Equilibrado (fp16)",
      precise: "Preciso (fp32)",
    };
    state.activeProfile = profile;
    elements.metricSpeed.textContent = labels[profile] || profile;
  }
  const queued = state.transcripts.filter((item) => item.status !== "completed").length;
  elements.metricQueue.textContent = queued;
  const usedSeconds = state.transcripts.reduce((acc, item) => acc + (item.duration_seconds || 0), 0);
  const quota = state.guest ? GUEST_QUOTA_MINUTES : 180;
  const remaining = Math.max(0, quota - Math.round(usedSeconds / 60));
  elements.metricMinutes.textContent = `${remaining} min`;
}

async function refreshLibrary(filters = null) {
  if (!state.token) {
    elements.libraryList.innerHTML = "<p class=\"form-hint\">Inicia sesión para ver tu biblioteca.</p>";
    return;
  }
  try {
    const params = new URLSearchParams();
    const formData = filters ? new FormData(filters) : new FormData(elements.libraryFilters);
    const search = formData.get("search");
    const status = formData.get("status");
    if (search) params.set("search", search.toString());
    if (status) params.set("status", status.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    const transcripts = await apiFetch(`/transcripts${query}`);
    state.transcripts = transcripts;
    renderLibrary();
    updateMetrics({ profile: state.activeProfile });
  } catch (error) {
    console.error(error);
    elements.libraryList.innerHTML = `<p class="form-hint">${error.message}</p>`;
  }
}

function renderLibrary() {
  if (!state.transcripts.length) {
    elements.libraryList.innerHTML = "<p class=\"form-hint\">Aún no tienes transcripciones. Sube tu primer audio.</p>";
    return;
  }
  const fragment = document.createDocumentFragment();
  state.transcripts.forEach((item) => {
    const card = document.createElement("article");
    card.className = "library__item";
    const header = document.createElement("div");
    header.className = "library__header";
    const title = document.createElement("div");
    title.innerHTML = `<strong>${item.title || "Sin título"}</strong><br/><small>${new Date(item.created_at).toLocaleString()}</small>`;
    const status = document.createElement("span");
    status.className = "chip";
    status.textContent = item.status;
    header.append(title, status);
    const tags = document.createElement("div");
    tags.className = "library__tags";
    (item.tags || []).forEach((tag) => {
      const span = document.createElement("span");
      span.className = "tag";
      span.textContent = tag;
      tags.append(span);
    });
    const meta = document.createElement("p");
    const duration = item.duration_seconds ? `${Math.round(item.duration_seconds / 6) / 10} min` : "–";
    meta.innerHTML = `Idioma: <strong>${item.language || "auto"}</strong> · Perfil: <strong>${item.quality_profile || "balanced"}</strong> · Duración: <strong>${duration}</strong>`;
    const actions = document.createElement("div");
    actions.className = "library__actions";

    const viewBtn = document.createElement("button");
    viewBtn.className = "btn";
    viewBtn.textContent = "Ver detalles";
    viewBtn.addEventListener("click", () => openTranscriptDetails(item.id));
    actions.append(viewBtn);

    if (item.status === "completed") {
      const downloadBtn = document.createElement("button");
      downloadBtn.className = "btn";
      downloadBtn.textContent = "Descargar TXT";
      downloadBtn.addEventListener("click", () => downloadTranscript(item.id, "txt"));
      actions.append(downloadBtn);

      const exportBtn = document.createElement("button");
      exportBtn.className = "btn";
      exportBtn.textContent = "Enviar a Notion";
      exportBtn.addEventListener("click", () => exportTranscript(item.id, "notion"));
      actions.append(exportBtn);

      const trelloBtn = document.createElement("button");
      trelloBtn.className = "btn";
      trelloBtn.textContent = "Enviar a Trello";
      trelloBtn.addEventListener("click", () => exportTranscript(item.id, "trello"));
      actions.append(trelloBtn);
    }

    card.append(header, tags, meta, actions);
    fragment.append(card);
  });
  elements.libraryList.innerHTML = "";
  elements.libraryList.append(fragment);
}

async function openTranscriptDetails(id) {
  try {
    const detail = await apiFetch(`/transcripts/${id}`);
    const text = detail.segments?.map((seg) => `• [${formatTimestamp(seg.start)} - ${formatTimestamp(seg.end)}] ${seg.text}`).join("\n") || "Sin contenido";
    const message = [`Título: ${detail.title || "Sin título"}`, `Estado: ${detail.status}`, `Etiquetas: ${(detail.tags || []).join(", ") || "ninguna"}`, "", text].join("\n");
    navigator.clipboard?.writeText(text).catch(() => {});
    alert(message);
  } catch (error) {
    showToast(error.message || "No se pudo abrir la transcripción", { tone: "error" });
  }
}

async function downloadTranscript(id, format) {
  try {
    const response = await fetch(`${API_BASE}/transcripts/${id}/download?format=${format}`, {
      headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
    });
    if (!response.ok) throw new Error("No se pudo descargar");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcripcion-${id}.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showToast(error.message || "Error al descargar", { tone: "error" });
  }
}

async function exportTranscript(id, destination) {
  try {
    await apiFetch(`/transcripts/${id}/export`, {
      method: "POST",
      body: JSON.stringify({ destination, format: destination === "trello" ? "md" : "txt" }),
    });
    showToast(`Exportación a ${destination} en progreso`);
  } catch (error) {
    showToast(error.message || "No se pudo exportar", { tone: "error" });
  }
}

function formatTimestamp(seconds) {
  const date = new Date((seconds || 0) * 1000);
  return date.toISOString().substr(11, 8);
}

function setupDragDrop() {
  const dropzone = elements.transcribeForm;
  dropzone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dropzone.classList.add("dropzone--active");
  });
  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("dropzone--active");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dropzone--active"));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dropzone--active");
    const files = event.dataTransfer?.files;
    if (files?.length) {
      dropzone.querySelector('input[type="file"]').files = files;
    }
  });
}

function setupRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    elements.recordStart.disabled = true;
    elements.recordStart.textContent = "Micrófono no disponible";
    return;
  }
  elements.recordStart.addEventListener("click", async () => {
    try {
      if (!state.audioContext) {
        state.audioContext = new AudioContext();
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.recorder = new MediaRecorder(stream);
      const source = state.audioContext.createMediaStreamSource(stream);
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 2048;
      source.connect(state.analyser);
      state.recordedChunks = [];
      state.recorder.ondataavailable = (event) => {
        if (event.data.size > 0) state.recordedChunks.push(event.data);
      };
      state.recorder.onstop = handleRecordingStop;
      state.recorder.start();
      elements.recordStart.disabled = true;
      elements.recordStop.disabled = false;
      elements.recordUpload.disabled = true;
      drawWaveform();
      showToast("Grabación iniciada");
    } catch (error) {
      showToast("No se pudo acceder al micrófono", { tone: "error" });
    }
  });

  elements.recordStop.addEventListener("click", () => {
    if (state.recorder?.state === "recording") {
      state.recorder.stop();
    }
  });

  elements.recordUpload.addEventListener("click", () => {
    if (!state.recordedBlob) return;
    const file = new File([state.recordedBlob], `grabacion-${Date.now()}.webm`, { type: state.recordedBlob.type });
    const fileInput = elements.transcribeForm.querySelector('input[type="file"]');
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
    setActiveTab("transcribe");
    showToast("Grabación lista para subir. Revisa el formulario de transcripción.");
  });
}

function drawWaveform() {
  if (!state.analyser) return;
  const canvas = elements.waveform;
  const ctx = canvas.getContext("2d");
  const bufferLength = state.analyser.fftSize;
  const dataArray = new Uint8Array(bufferLength);

  const draw = () => {
    state.animationFrame = requestAnimationFrame(draw);
    state.analyser.getByteTimeDomainData(dataArray);
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(59, 130, 246, 0.8)";
    ctx.beginPath();
    const sliceWidth = (canvas.width * 1.0) / bufferLength;
    let x = 0;
    let peak = 0;
    for (let i = 0; i < bufferLength; i += 1) {
      const v = dataArray[i] / 128.0;
      const y = (v * canvas.height) / 2;
      peak = Math.max(peak, Math.abs(v - 1));
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
      x += sliceWidth;
    }
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.stroke();
    const level = Math.min(100, Math.round(peak * 100));
    elements.meterBar.style.width = `${level}%`;
  };
  draw();
}

function handleRecordingStop() {
  cancelAnimationFrame(state.animationFrame);
  elements.meterBar.style.width = "0%";
  const blob = new Blob(state.recordedChunks, { type: state.recorder.mimeType });
  state.recordedBlob = blob;
  elements.recordPreview.src = URL.createObjectURL(blob);
  elements.recordPreview.hidden = false;
  elements.recordStart.disabled = false;
  elements.recordStop.disabled = true;
  elements.recordUpload.disabled = false;
  showToast("Grabación lista. Puedes subirla.");
}

function bindEvents() {
  elements.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
  });

  document.querySelector('[data-action="cancel-stream"]').addEventListener("click", () => {
    if (state.streamController) {
      state.streamController.abort();
    }
  });

  document.querySelector('[data-action="view-library"]').addEventListener("click", () => {
    setActiveTab("library");
  });

  document.querySelector('[data-action="logout"]').addEventListener("click", () => {
    clearAuth();
    resetStream();
  });

  if (elements.heroAuth) {
    elements.heroAuth.addEventListener("click", () => {
      toggleAuthPanel(true);
      setActiveTab("account");
    });
  }

  elements.heroTranscribe.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      if (!state.token) {
        startGuestSession().catch((error) => {
          console.error(error);
          toggleAuthPanel(true);
        });
      }
      setActiveTab("transcribe");
    });
  });

  if (elements.accountButton) {
    elements.accountButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      setAccountMenu(!isAccountMenuOpen());
    });
  }

  elements.accountMenuItems.forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      const action = event.currentTarget?.dataset.menuAction;
      setAccountMenu(false);
      if (action === "signup") {
        toggleAuthPanel(true);
        setActiveTab("account");
        elements.signupForm?.querySelector('input[name="email"]')?.focus();
      } else if (action === "login") {
        toggleAuthPanel(true);
        setActiveTab("account");
        elements.loginForm?.querySelector('input[name="email"]')?.focus();
      } else if (action === "guest") {
        startGuestSession().catch((error) => {
          console.error(error);
          toggleAuthPanel(true);
        });
        setActiveTab("transcribe");
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (!isAccountMenuOpen()) return;
    if (
      elements.accountMenu?.contains(event.target) ||
      elements.accountButton?.contains(event.target)
    ) {
      return;
    }
    setAccountMenu(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isAccountMenuOpen()) {
      setAccountMenu(false);
      elements.accountButton?.focus();
    }
  });

  elements.signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = data.get("email");
    const password = data.get("password");
    try {
      await signup(email, password);
    } catch (error) {
      showToast(error.message || "No se pudo crear la cuenta", { tone: "error" });
    }
  });

  elements.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = data.get("email");
    const password = data.get("password");
    try {
      await login(email, password);
    } catch (error) {
      showToast(error.message || "Credenciales incorrectas", { tone: "error" });
    }
  });

  elements.transcribeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.token) {
      showToast("Inicia sesión para transcribir", { tone: "error" });
      toggleAuthPanel(true);
      return;
    }
    const formData = new FormData(event.currentTarget);
    const file = formData.get("file");
    if (!file || !(file instanceof File)) {
      showToast("Selecciona un archivo de audio", { tone: "error" });
      return;
    }
    if (!formData.get("language")) formData.delete("language");
    state.activeProfile = formData.get("profile") || "balanced";
    updateMetrics({ profile: state.activeProfile });
    try {
      updateProgress(0);
      const job = await uploadAudio(formData, {
        onProgress: (progress) => updateProgress(progress),
      });
      showToast("Audio subido. Procesando...");
      streamTranscription(job.job_id);
    } catch (error) {
      console.error(error);
      showToast(error.message || "No se pudo transcribir", { tone: "error" });
    }
  });

  elements.libraryFilters.addEventListener("submit", (event) => {
    event.preventDefault();
    refreshLibrary(event.currentTarget);
  });
}

function init() {
  readStoredAuth();
  updateAccount();
  setAccountMenu(false);
  bindEvents();
  setupDragDrop();
  setupRecording();
  setActiveTab("transcribe");
  if (state.token) {
    refreshLibrary();
  }
}

init();
