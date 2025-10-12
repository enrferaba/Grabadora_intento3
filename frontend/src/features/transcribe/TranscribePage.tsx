import { useEffect, useRef, useState } from "react";
import { qualityProfiles, streamTranscription, uploadTranscription } from "@/lib/api";
import { SseViewer } from "@/features/transcribe/components/SseViewer";
import { Uploader } from "@/features/transcribe/components/Uploader";
import { TranscriptionHistory } from "@/features/transcribe/components/TranscriptionHistory";

interface Props {
  onLibraryRefresh?: () => void;
}

type FlowStatus = "idle" | "uploading" | "streaming" | "completed" | "error" | "recording";

export function TranscribePage({ onLibraryRefresh }: Props) {
  const [language, setLanguage] = useState("auto");
  const [profile, setProfile] = useState("balanced");
  const [tags, setTags] = useState("reunión, minutos");
  const [title, setTitle] = useState("");
  const [tokens, setTokens] = useState<Array<{ text: string; t0: number; t1: number }>>([]);
  const [status, setStatus] = useState<FlowStatus>("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [completedPayload, setCompletedPayload] = useState<Record<string, unknown> | null>(null);
  const [diarization, setDiarization] = useState(false);
  const [wordTimestamps, setWordTimestamps] = useState(true);
  const stopStreamRef = useRef<() => void>();
  const [viewerFontSize, setViewerFontSize] = useState(1.1);
  const [viewerFullscreen, setViewerFullscreen] = useState(false);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);

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
        setHistoryRefreshToken((value) => value + 1);
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
    setViewerFullscreen(false);
  }

  const statusPalette: Record<FlowStatus, string> = {
    idle: "rgba(148, 163, 184, 0.45)",
    uploading: "rgba(59, 130, 246, 0.65)",
    streaming: "rgba(56, 189, 248, 0.85)",
    completed: "rgba(34, 197, 94, 0.85)",
    error: "rgba(239, 68, 68, 0.85)",
    recording: "rgba(244, 114, 182, 0.85)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2.5rem", width: "100%" }}>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(320px, 1fr) minmax(420px, 1.1fr)",
          gap: "2rem",
          alignItems: "stretch",
          width: "100%",
        }}
      >
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem", padding: "2rem" }}>
          <header style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "1.65rem" }}>Sube y transcribe</h2>
                <p style={{ margin: 0, color: "#94a3b8", lineHeight: 1.6 }}>
                  Selecciona tu archivo y recibe la transcripción en vivo al instante.
                </p>
              </div>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.35rem 0.85rem",
                  borderRadius: "999px",
                  background: statusPalette[status],
                  color: "#0f172a",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                {status === "idle" && "Listo"}
                {status === "uploading" && `Subiendo ${uploadProgress}%`}
                {status === "streaming" && "Transcribiendo"}
                {status === "completed" && "Completado"}
                {status === "error" && "Error"}
              </span>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {qualityProfiles().map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setProfile(item.id)}
                  style={{
                    borderRadius: "999px",
                    padding: "0.35rem 0.95rem",
                    border: profile === item.id ? "1px solid #38bdf8" : "1px solid rgba(148,163,184,0.35)",
                    background: profile === item.id ? "rgba(56,189,248,0.18)" : "rgba(15,23,42,0.55)",
                    color: "#e2e8f0",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <strong style={{ display: "block", fontSize: "0.85rem" }}>{item.title}</strong>
                  <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>{item.description}</span>
                </button>
              ))}
            </div>
          </header>

          <Uploader onSelect={handleSubmit} busy={status === "uploading" || status === "streaming"} />

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
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
              Título (opcional)
              <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Reunión semanal" />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              Etiquetas (opcional)
              <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="reunión, sprint, tareas" />
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

          {status === "uploading" && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                background: "rgba(56,189,248,0.12)",
                borderRadius: "12px",
                padding: "0.75rem 1rem",
                color: "#e0f2fe",
              }}
            >
              <span style={{ fontSize: "0.8rem", letterSpacing: "0.05em" }}>Subiendo {uploadProgress}%</span>
              <div style={{ flex: 1, height: "6px", background: "rgba(148,163,184,0.3)", borderRadius: "999px" }}>
                <div
                  style={{
                    width: `${uploadProgress}%`,
                    height: "100%",
                    borderRadius: "999px",
                    background: "linear-gradient(90deg, #38bdf8, #60a5fa)",
                    transition: "width 0.2s ease",
                  }}
                />
              </div>
            </div>
          )}

          {(status === "completed" || status === "error") && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
              <div style={{ color: status === "completed" ? "#22c55e" : "#fca5a5" }}>
                {status === "completed"
                  ? "Transcripción completada. Revisa tu historial para descargarla."
                  : error ?? "No se pudo completar la transcripción."}
              </div>
              <button
                type="button"
                onClick={resetFlow}
                style={{
                  borderRadius: "999px",
                  border: "1px solid rgba(148,163,184,0.35)",
                  background: "transparent",
                  color: "#cbd5f5",
                  padding: "0.55rem 1.4rem",
                  cursor: "pointer",
                }}
              >
                Nuevo audio
              </button>
            </div>
          )}
        </div>

        <SseViewer
          tokens={tokens}
          status={status}
          error={error}
          onRetry={() => jobId && startStream({ job_id: jobId })}
          fontSize={viewerFontSize}
          onFontSizeChange={(size) => setViewerFontSize(Math.min(Math.max(size, 0.8), 2.4))}
          fullscreen={viewerFullscreen}
          onToggleFullscreen={() => setViewerFullscreen((value) => !value)}
        />
      </section>

      <TranscriptionHistory refreshKey={historyRefreshToken} onSelect={() => setViewerFullscreen(false)} />

    </div>
  );
}
