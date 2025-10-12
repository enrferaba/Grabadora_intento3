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
  tags: string[];
}

export interface TranscriptDetail extends TranscriptSummary {
  audio_key: string;
  transcript_key?: string | null;
  transcript_url?: string | null;
  segments: Array<{ start: number; end: number; text: string }>;
  error_message?: string | null;
  profile_id?: number | null;
}

export interface StreamHandlers {
  onDelta?: (delta: { text: string; t0: number; t1: number }) => void;
  onCompleted?: (payload: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
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

export function qualityProfiles(): Array<{ id: string; title: string; description: string }> {
  return [
    { id: "fast", title: "Rápido (int8)", description: "Ideal para notas rápidas y demo" },
    { id: "balanced", title: "Equilibrado (float16)", description: "La mejor relación coste/precisión" },
    { id: "precise", title: "Preciso (float32)", description: "Máxima fidelidad para entrevistas" },
  ];
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
        const detail = typeof xhr.response === "string" ? xhr.response : JSON.stringify(xhr.response);
        reject(new Error(detail || `Upload failed with status ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("No se pudo subir el audio. Comprueba tu conexión."));
    xhr.onabort = () => reject(new Error("Subida cancelada"));
    xhr.send(formData);
  });
}

function parseEventStream(chunk: string, handlers: StreamHandlers): void {
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
    try {
      const payload = JSON.parse(payloadText);
      if (eventType === "delta") {
        handlers.onDelta?.(payload);
      } else if (eventType === "completed") {
        handlers.onCompleted?.(payload);
      } else if (eventType === "error") {
        handlers.onError?.(new Error(payload.detail ?? payloadText));
      }
    } catch (error) {
      if (eventType === "delta") {
        handlers.onDelta?.({ text: payloadText, t0: 0, t1: 0 });
      } else if (eventType === "error") {
        handlers.onError?.(error as Error);
      }
    }
  }
}

export function streamTranscription(jobId: string, handlers: StreamHandlers): () => void {
  const controller = new AbortController();
  const auth = getAuthState();
  (async () => {
    try {
      const response = await fetch(`${API_BASE}/transcribe/${jobId}`, {
        headers: auth?.token ? { Authorization: `Bearer ${auth.token}` } : undefined,
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`No se pudo abrir el stream (${response.status})`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lastSeparator = buffer.lastIndexOf("\n\n");
        if (lastSeparator !== -1) {
          const chunk = buffer.slice(0, lastSeparator);
          parseEventStream(chunk, handlers);
          buffer = buffer.slice(lastSeparator + 2);
        }
      }
      if (buffer.trim()) {
        parseEventStream(buffer, handlers);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        handlers.onError?.(error as Error);
      }
    }
  })();
  return () => controller.abort();
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

export { getAuthState, setAuthState, clearAuthState } from "./auth";
