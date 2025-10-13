import { clearAuthState, getAuthState, setAuthState } from "./auth";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface SignupPayload {
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TranscriptSummary {
  id: number;
  job_id: string;
  status: string;
  title?: string | null;
  language?: string | null;
  quality_profile?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
  runtime_seconds?: number | null;
  model_size?: string | null;
  device_preference?: string | null;
  beam_size?: number | null;
  subject?: string | null;
  output_folder?: string | null;
  premium_enabled?: boolean | null;
  premium_notes?: string | null;
  premium_perks?: string[] | null;
  error_message?: string | null;
  debug_events?: Array<Record<string, unknown>>;
  tags: string[];
  notes?: string | null;
}

export interface TranscriptDetail extends TranscriptSummary {
  audio_key: string;
  transcript_key?: string | null;
  transcript_url?: string | null;
  segments: Array<{ start: number; end: number; text: string }>;
  stored_path?: string | null;
  transcript_path?: string | null;
  text?: string | null;
  speakers?: Array<Record<string, unknown>>;
  original_filename?: string | null;
  error_message?: string | null;
  profile_id?: number | null;
}

export interface QualityProfile {
  id: string;
  label: string;
  description?: string | null;
  latency_hint_ms?: number | null;
  cost_factor?: number | null;
}

export interface AccountProfile {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface ProfilesResponse {
  quality_profiles: QualityProfile[];
  account_profiles: AccountProfile[];
}

export interface AppConfig {
  app_name: string;
  max_upload_size_mb: number;
  queue_backend: "auto" | "redis" | "memory";
  sse_ping_interval: number;
  sse_retry_delay_ms: number;
  metrics_enabled: boolean;
  spa_routes: string[];
  storage_ready: boolean;
  features: Record<string, unknown>;
}

const DEFAULT_QUALITY_PROFILES: QualityProfile[] = [
  {
    id: "fast",
    label: "Rápido (int8)",
    description: "Máxima velocidad, ideal para notas rápidas",
    latency_hint_ms: 60000,
    cost_factor: 0.25,
  },
  {
    id: "balanced",
    label: "Equilibrado (float16)",
    description: "Buen balance entre precisión y coste",
    latency_hint_ms: 120000,
    cost_factor: 1,
  },
  {
    id: "precise",
    label: "Preciso (float32)",
    description: "Máxima fidelidad para grabaciones críticas",
    latency_hint_ms: 180000,
    cost_factor: 1.75,
  },
];

let cachedProfiles: ProfilesResponse | null = null;
let cachedConfig: AppConfig | null = null;
let profilesPromise: Promise<ProfilesResponse> | null = null;
let configPromise: Promise<AppConfig> | null = null;

export function getCachedQualityProfiles(): QualityProfile[] {
  return cachedProfiles?.quality_profiles ?? DEFAULT_QUALITY_PROFILES;
}

export function getCachedAccountProfiles(): AccountProfile[] {
  return cachedProfiles?.account_profiles ?? [];
}

export function getCachedConfig(): AppConfig | null {
  return cachedConfig;
}

export function hasProfileCache(): boolean {
  return cachedProfiles !== null;
}

export function hasConfigCache(): boolean {
  return cachedConfig !== null;
}

export async function fetchProfiles(force = false): Promise<ProfilesResponse> {
  if (!force && cachedProfiles) {
    return cachedProfiles;
  }
  if (!force && profilesPromise) {
    return profilesPromise;
  }
  profilesPromise = apiFetch<ProfilesResponse>("/profiles");
  try {
    cachedProfiles = await profilesPromise;
    return cachedProfiles;
  } finally {
    profilesPromise = null;
  }
}

export async function fetchAppConfig(force = false): Promise<AppConfig> {
  if (!force && cachedConfig) {
    return cachedConfig;
  }
  if (!force && configPromise) {
    return configPromise;
  }
  configPromise = apiFetch<AppConfig>("/config");
  try {
    cachedConfig = await configPromise;
    return cachedConfig;
  } finally {
    configPromise = null;
  }
}

export interface StreamHandlers {
  onDelta?: (delta: { text: string; t0: number; t1: number }) => void;
  onSnapshot?: (payload: { text: string; progress: number; segments?: Array<{ start: number; end: number; text: string }> }) => void;
  onCompleted?: (payload: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
  onHeartbeat?: (payload: { status?: string; progress?: number; segment?: number }) => void;
}

export interface UploadOptions {
  onProgress?: (progress: number) => void;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const auth = getAuthState();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (!headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (auth?.token) {
    headers.set("Authorization", `Bearer ${auth.token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as unknown as T;
  }
  const contentType = response.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as unknown as T;
}

export async function signup(payload: SignupPayload): Promise<void> {
  await apiFetch("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginPayload): Promise<void> {
  const body = new URLSearchParams();
  body.append("username", payload.email);
  body.append("password", payload.password);
  body.append("grant_type", "password");
  const response = await apiFetch<LoginResponse>("/auth/token", {
    method: "POST",
    body,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  setAuthState({ token: response.access_token, email: payload.email });
}

export function logout(): void {
  clearAuthState();
}

export async function uploadTranscription(formData: FormData, options: UploadOptions = {}): Promise<{
  job_id: string;
  status: string;
  quality_profile?: string;
}> {
  const auth = getAuthState();
  return await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/transcribe`);
    xhr.responseType = "json";
    if (auth?.token) {
      xhr.setRequestHeader("Authorization", `Bearer ${auth.token}`);
    }
    if (xhr.upload && options.onProgress) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          options.onProgress?.(event.loaded / event.total);
        }
      };
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
      } else {
        let detail = typeof xhr.response === "string" ? xhr.response : JSON.stringify(xhr.response);
        if (xhr.status === 413) {
          const limit = cachedConfig?.max_upload_size_mb ?? getCachedConfig()?.max_upload_size_mb;
          detail = limit
            ? `El archivo supera el límite permitido de ${limit} MB.`
            : "El archivo es demasiado grande para procesarlo.";
        }
        reject(new Error(detail || `Upload failed with status ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("No se pudo subir el audio. Comprueba tu conexión."));
    xhr.onabort = () => reject(new Error("Subida cancelada"));
    xhr.send(formData);
  });
}

interface StreamState {
  completed: boolean;
  failed: boolean;
  lastEventTs: number;
}

function parseEventStream(chunk: string, handlers: StreamHandlers, state: StreamState): void {
  const events = chunk.split("\n\n");
  for (const event of events) {
    if (!event.trim()) continue;
    const lines = event.split("\n");
    let eventType = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventType = line.replace("event:", "").trim();
      } else if (line.startsWith("data:")) {
        data += `${line.replace("data:", "").trim()}\n`;
      }
    }
    const payloadText = data.trim();
    if (!payloadText) continue;
    const now = Date.now();
    state.lastEventTs = now;
    try {
      const payload = JSON.parse(payloadText);
      if (eventType === "delta") {
        handlers.onDelta?.(payload);
      } else if (eventType === "completed") {
        state.completed = true;
        handlers.onCompleted?.(payload);
      } else if (eventType === "error") {
        state.failed = true;
        handlers.onError?.(new Error(payload.detail ?? payloadText));
      } else if (eventType === "snapshot") {
        handlers.onSnapshot?.(payload);
      } else if (eventType === "heartbeat") {
        handlers.onHeartbeat?.(payload);
      }
    } catch (error) {
      if (eventType === "delta") {
        handlers.onDelta?.({ text: payloadText, t0: 0, t1: 0 });
      } else if (eventType === "error") {
        state.failed = true;
        handlers.onError?.(error as Error);
      } else if (eventType === "snapshot") {
        handlers.onSnapshot?.({ text: payloadText, progress: 0, segments: [] });
      }
    }
  }
}

export function streamTranscription(jobId: string, handlers: StreamHandlers): () => void {
  const state: StreamState = {
    completed: false,
    failed: false,
    lastEventTs: Date.now(),
  };

  let stopped = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let heartbeatMonitor: ReturnType<typeof setInterval> | null = null;
  let currentController: AbortController | null = null;
  let reconnectAttempts = 0;
  let lastError: Error | null = null;

  const MAX_RECONNECT_ATTEMPTS = 5;
  const HEARTBEAT_TIMEOUT_MS = 20000;

  const cleanupTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (heartbeatMonitor) {
      clearInterval(heartbeatMonitor);
      heartbeatMonitor = null;
    }
  };

  const scheduleReconnect = () => {
    if (stopped || state.completed || state.failed) {
      return;
    }
    if (reconnectTimer) {
      return;
    }
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      state.failed = true;
      cleanupTimer();
      handlers.onError?.(lastError ?? new Error("Se perdió la conexión del stream"));
      return;
    }
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 10000);
    reconnectAttempts += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (!stopped && !state.completed && !state.failed) {
        openStream();
      }
    }, delay);
  };

  const openStream = async () => {
    if (stopped || state.completed || state.failed) {
      return;
    }
    const controller = new AbortController();
    currentController = controller;
    const auth = getAuthState();
    let streamError: Error | null = null;
    try {
      const response = await fetch(`${API_BASE}/transcribe/${jobId}`, {
        headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`No se pudo abrir el stream (${response.status})`);
      }
      reconnectAttempts = 0;
      lastError = null;
      state.lastEventTs = Date.now();
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (!stopped && !state.completed && !state.failed) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const lastSeparator = buffer.lastIndexOf("\n\n");
        if (lastSeparator !== -1) {
          const chunk = buffer.slice(0, lastSeparator);
          parseEventStream(chunk, handlers, state);
          buffer = buffer.slice(lastSeparator + 2);
        }
      }
      if (buffer.trim() && !state.completed && !state.failed) {
        parseEventStream(buffer, handlers, state);
      }
    } catch (error) {
      if (controller.signal.aborted || stopped || state.completed || state.failed) {
        return;
      }
      streamError = error as Error;
      lastError = streamError;
    } finally {
      if (stopped || state.completed || state.failed) {
        cleanupTimer();
        return;
      }
      scheduleReconnect();
    }
  };

  openStream();

  heartbeatMonitor = setInterval(() => {
    if (stopped || state.completed || state.failed) {
      cleanupTimer();
      return;
    }
    const idleMs = Date.now() - state.lastEventTs;
    if (idleMs > HEARTBEAT_TIMEOUT_MS) {
      if (currentController && !currentController.signal.aborted) {
        currentController.abort();
      }
      scheduleReconnect();
    }
  }, HEARTBEAT_TIMEOUT_MS / 2);

  return () => {
    stopped = true;
    cleanupTimer();
    if (currentController && !currentController.signal.aborted) {
      currentController.abort();
    }
  };
}

export async function listTranscripts(params: { search?: string; status?: string } = {}): Promise<TranscriptSummary[]> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.status) query.set("status", params.status);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch(`/transcripts${suffix}`);
}

export async function getTranscript(id: number): Promise<TranscriptDetail> {
  return apiFetch(`/transcripts/${id}`);
}

export async function downloadTranscript(id: number, format: "txt" | "md" | "srt" = "txt"): Promise<void> {
  const auth = getAuthState();
  const response = await fetch(`${API_BASE}/transcripts/${id}/download?format=${format}`, {
    headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `No se pudo descargar (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `transcript-${id}.${format}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export async function exportTranscript(
  id: number,
  destination: "notion" | "trello" | "webhook",
  format: "txt" | "md" | "srt" = "txt",
  note?: string,
): Promise<void> {
  await apiFetch(`/transcripts/${id}/export`, {
    method: "POST",
    body: JSON.stringify({ destination, format, note }),
  });
}

export async function updateTranscript(
  id: number,
  payload: Partial<Pick<TranscriptDetail, "title" | "tags" | "notes" | "quality_profile">>,
): Promise<TranscriptDetail> {
  const body: Record<string, unknown> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.notes !== undefined) body.notes = payload.notes;
  if (payload.quality_profile !== undefined) body.quality_profile = payload.quality_profile;
  if (payload.tags !== undefined) body.tags = payload.tags;
  return apiFetch(`/transcripts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteTranscript(id: number): Promise<void> {
  await apiFetch(`/transcripts/${id}`, { method: "DELETE" });
}

export { getAuthState, setAuthState, clearAuthState } from "./auth";
