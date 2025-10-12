import { useEffect, useRef, useState } from "react";
import { qualityProfiles, streamTranscription, uploadTranscription } from "@/lib/api";
import { AuthPanel } from "@/components/AuthPanel";
import { SseViewer } from "@/components/SseViewer";
import { Uploader } from "@/components/Uploader";

interface Props {
  onLibraryRefresh?: () => void;
  requireAuth?: boolean;
}

export function TranscribirPage({ onLibraryRefresh, requireAuth = true }: Props) {
  const [language, setLanguage] = useState("auto");
  const [profile, setProfile] = useState("balanced");
  const [tags, setTags] = useState("reunión, minutos");
  const [title, setTitle] = useState("");
  const [tokens, setTokens] = useState<Array<{ text: string; t0: number; t1: number }>>([]);
  const [status, setStatus] = useState<"idle" | "uploading" | "streaming" | "completed" | "error">("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [completedPayload, setCompletedPayload] = useState<Record<string, unknown> | null>(null);
  const [diarization, setDiarization] = useState(false);
  const [wordTimestamps, setWordTimestamps] = useState(true);
  const stopStreamRef = useRef<() => void>();

  useEffect(() => () => stopStreamRef.current?.(), []);

  async function startStream(job: { job_id: string }) {
    setJobId(job.job_id);
    setStatus("streaming");
    stopStreamRef.current?.();
    stopStreamRef.current = streamTranscription(job.job_id, {
      onDelta(delta) {
        setTokens((previous) => [...previous, delta]);
      },
      onCompleted(payload) {
        setStatus("completed");
        setCompletedPayload(payload);
        onLibraryRefresh?.();
      },
      onError(err) {
        setError(err.message);
        setStatus("error");
      },
    });
  }

  async function handleSubmit(file: File) {
    setTokens([]);
    setError(null);
    setStatus("uploading");
    const formData = new FormData();
    formData.append("file", file);
    if (language !== "auto") {
      formData.append("language", language);
    }
    formData.append("profile", profile);
    if (title) formData.append("title", title);
    if (tags) formData.append("tags", tags);
    formData.append("diarization", String(diarization));
    formData.append("word_timestamps", String(wordTimestamps));
    try {
      const job = await uploadTranscription(formData, {
        onProgress: (value) => setUploadProgress(Math.round(value * 100)),
      });
      setStatus("streaming");
      await startStream(job);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo iniciar la transcripción";
      setError(message);
      setStatus("error");
    }
  }

    function resetFlow() {
      stopStreamRef.current?.();
      setTokens([]);
      setStatus("idle");
      setError(null);
      setJobId(null);
      setCompletedPayload(null);
    }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem", width: "100%" }}>
      <section style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: "2rem", alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <header>
              <h2 style={{ margin: 0 }}>Transcribir</h2>
              <p style={{ margin: 0, color: "#94a3b8" }}>
                Sube un archivo o grábalo en la pestaña "Grabar". Seguimos cada token en vivo por SSE.
              </p>
            </header>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                Idioma
                <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                  <option value="auto">Automático</option>
                  <option value="es">Español</option>
                  <option value="en">Inglés</option>
                  <option value="fr">Francés</option>
                  <option value="de">Alemán</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                Perfil de calidad
                <select value={profile} onChange={(event) => setProfile(event.target.value)}>
                  {qualityProfiles().map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                Etiquetas
                <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="reunión, sprint, tareas" />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                Título
                <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Reunión semanal" />
              </label>
            </div>
            <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={diarization} onChange={(event) => setDiarization(event.target.checked)} />
                Diarización experimental
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={wordTimestamps} onChange={(event) => setWordTimestamps(event.target.checked)} />
                Marcas temporales por palabra
              </label>
            </div>
            <Uploader onSelect={handleSubmit} busy={status === "uploading" || status === "streaming"} />
            {status === "uploading" && (
              <div style={{ color: "#cbd5f5" }}>Subiendo... {uploadProgress}%</div>
            )}
            {status === "completed" && completedPayload && (
              <div style={{ color: "#22c55e" }}>
                ¡Listo! Exporta a TXT, Markdown o SRT desde la Biblioteca. Job: {completedPayload["job_id"] as string}
              </div>
            )}
            {status === "error" && error && (
              <div style={{ color: "#fca5a5" }}>{error}</div>
            )}
            {(status === "completed" || status === "error") && (
              <button
                type="button"
                onClick={resetFlow}
                style={{
                  borderRadius: "999px",
                  border: "1px solid rgba(148,163,184,0.35)",
                  background: "transparent",
                  color: "#cbd5f5",
                  padding: "0.65rem 1.5rem",
                  cursor: "pointer",
                  alignSelf: "flex-start",
                }}
              >
                Empezar otra transcripción
              </button>
            )}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {requireAuth && <AuthPanel onAuthenticated={onLibraryRefresh} onLogout={onLibraryRefresh} />}
          <SseViewer tokens={tokens} status={status} error={error} onRetry={() => jobId && startStream({ job_id: jobId })} />
        </div>
      </section>
    </div>
  );
}
