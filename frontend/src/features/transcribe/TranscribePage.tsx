import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { downloadTranscript, streamTranscription, uploadTranscription } from "@/lib/api";
import { SseViewer } from "@/features/transcribe/components/SseViewer";
import { TranscriptionHistory } from "@/features/transcribe/components/TranscriptionHistory";
import { MessageBanner } from "@/components/MessageBanner";
import { Uploader, type UploaderHandle } from "@/features/transcribe/components/Uploader";
import { useAppConfig, useQualityProfiles } from "@/lib/hooks";

interface Props {
  onLibraryRefresh?: () => void;
}

type FlowStatus = "idle" | "uploading" | "streaming" | "completed" | "error" | "recording";
type TranscriptFormat = "txt" | "md" | "srt";

function tokensFromSnapshot(text: string): Array<{ text: string; t0: number; t1: number }> {
  if (!text) return [];
  const parts = text.match(/\s+|\S+/g) ?? [];
  return parts.map((chunk, index) => ({ text: chunk, t0: index, t1: index }));
}

export function TranscribePage({ onLibraryRefresh }: Props) {
  const navigate = useNavigate();
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
  const [heartbeatMeta, setHeartbeatMeta] = useState<{ status?: string; progress?: number; segment?: number } | null>(null);
  const stopStreamRef = useRef<() => void>();
  const [viewerFontSize, setViewerFontSize] = useState(1.1);
  const [viewerFullscreen, setViewerFullscreen] = useState(false);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);
  const { profiles } = useQualityProfiles();
  const { config } = useAppConfig();
  const uploaderRef = useRef<UploaderHandle | null>(null);
  const [actionBanner, setActionBanner] = useState<{ tone: "success" | "error" | "info"; message: string } | null>(null);
  const [downloadFormat, setDownloadFormat] = useState<TranscriptFormat>("txt");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => () => stopStreamRef.current?.(), []);

  useEffect(() => {
    if (profiles.length > 0 && !profiles.find((item) => item.id === profile)) {
      setProfile(profiles[0].id);
    }
  }, [profiles, profile]);
  useEffect(() => {
    if (!actionBanner || actionBanner.tone === "error") {
      return;
    }
    const timer = window.setTimeout(() => setActionBanner(null), 6000);
    return () => window.clearTimeout(timer);
  }, [actionBanner]);

  async function startStream(job: { job_id: string }) {
    setJobId(job.job_id);
    setStatus("streaming");
    setHeartbeatMeta(null);
    stopStreamRef.current?.();
    setActionBanner(null);
    stopStreamRef.current = streamTranscription(job.job_id, {
      onDelta(delta) {
        setTokens((previous) => [...previous, delta]);
      },
      onSnapshot(payload) {
        const text = typeof payload.text === "string" ? payload.text : "";
        setTokens(tokensFromSnapshot(text));
        setHeartbeatMeta((previous) => ({ ...(previous ?? {}), progress: payload.progress }));
      },
      onCompleted(payload) {
        setStatus("completed");
        setCompletedPayload(payload);
        onLibraryRefresh?.();
        setHistoryRefreshToken((value) => value + 1);
        setActionBanner({ tone: "success", message: "Transcripción completada. Puedes descargarla o revisarla en tu biblioteca." });
      },
      onError(err) {
        setError(err.message);
        setStatus("error");
        setActionBanner({ tone: "error", message: err.message });
      },
      onHeartbeat(payload) {
        setHeartbeatMeta(payload);
      },
    });
  }

  async function handleSubmit(file: File) {
    setTokens([]);
    setError(null);
    setStatus("uploading");
    setActionBanner({ tone: "info", message: "Subiendo tu archivo. Comenzaremos a transcribir en cuanto finalice." });
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
      setActionBanner({ tone: "error", message });
    }
  }

  function resetFlow() {
    stopStreamRef.current?.();
    setTokens([]);
    setStatus("idle");
    setError(null);
    setJobId(null);
    setCompletedPayload(null);
    setHeartbeatMeta(null);
    setViewerFullscreen(false);
    setUploadProgress(0);
    setActionBanner(null);
    setDownloading(false);
  }

  const statusPalette: Record<FlowStatus, string> = {
    idle: "rgba(148, 163, 184, 0.45)",
    uploading: "rgba(59, 130, 246, 0.65)",
    streaming: "rgba(56, 189, 248, 0.85)",
    completed: "rgba(34, 197, 94, 0.85)",
    error: "rgba(239, 68, 68, 0.85)",
    recording: "rgba(244, 114, 182, 0.85)",
  };

  const isBusy = status === "uploading" || status === "streaming" || status === "recording";
  const completedId = typeof completedPayload?.id === "number" ? (completedPayload.id as number) : null;
  const transcriptUrl = typeof completedPayload?.transcript_url === "string" ? (completedPayload.transcript_url as string) : null;
  const detailTitle = (completedPayload?.title as string | undefined) ?? undefined;

  const availableLanguages = useMemo(
    () => [
      { value: "auto", label: "Automático" },
      { value: "es", label: "Español" },
      { value: "en", label: "Inglés" },
      { value: "fr", label: "Francés" },
      { value: "de", label: "Alemán" },
      { value: "pt", label: "Portugués" },
    ],
    [],
  );

  async function handleQuickDownload(format: TranscriptFormat) {
    if (!completedId) {
      setActionBanner({ tone: "error", message: "Descarga no disponible. Revisa tu biblioteca para más detalles." });
      return;
    }
    setDownloading(true);
    try {
      await downloadTranscript(completedId, format);
      setActionBanner({
        tone: "success",
        message: `La descarga en formato ${format.toUpperCase()} ha comenzado${detailTitle ? ` para "${detailTitle}"` : ""}.`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo descargar la transcripción";
      setActionBanner({ tone: "error", message });
    } finally {
      setDownloading(false);
    }
  }

  function handleOpenLibrary() {
    navigate("/biblioteca");
  }

  function handleStartRecording() {
    navigate("/grabar");
  }

  function handleOpenTranscriptUrl() {
    if (!transcriptUrl) {
      setActionBanner({ tone: "error", message: "Todavía no hay un enlace público para esta transcripción." });
      return;
    }
    window.open(transcriptUrl, "_blank", "noopener");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2.5rem", width: "100%" }}>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: "1.25rem", padding: "2rem" }}>
        <header style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
          <h1 style={{ margin: 0, fontSize: "1.85rem" }}>Transcribe sin fricción</h1>
          <p style={{ margin: 0, color: "#94a3b8", maxWidth: "60ch" }}>
            Sube un archivo, grábalo en directo o revisa tu biblioteca. Todos los botones se mantienen activos solo cuando la acción está disponible, para que siempre tengas claro el siguiente paso.
          </p>
        </header>
        {(actionBanner || error) && (
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {error && (
              <MessageBanner tone="error" onClose={() => setError(null)}>
                {error}
              </MessageBanner>
            )}
            {actionBanner && (
              <MessageBanner tone={actionBanner.tone} onClose={() => setActionBanner(null)}>
                {actionBanner.message}
              </MessageBanner>
            )}
          </div>
        )}
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button
            className="primary"
            type="button"
            onClick={() => uploaderRef.current?.open()}
            disabled={isBusy}
          >
            {isBusy ? "Procesando audio…" : "Seleccionar archivo"}
          </button>
          <button className="secondary" type="button" onClick={handleStartRecording}>
            Grabar desde el navegador
          </button>
          <button
            type="button"
            onClick={handleOpenLibrary}
            style={{
              borderRadius: "999px",
              border: "1px solid rgba(148,163,184,0.35)",
              background: "transparent",
              color: "#cbd5f5",
              padding: "0.65rem 1.4rem",
              cursor: "pointer",
            }}
          >
            Abrir biblioteca
          </button>
        </div>
      </section>

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
                {status === "streaming" && (
                  <>
                    Transcribiendo
                    {typeof heartbeatMeta?.progress === "number" && heartbeatMeta.progress > 0 && (
                      <span style={{ fontWeight: 500, marginLeft: "0.35rem", fontSize: "0.75rem" }}>
                        · {heartbeatMeta.progress} tokens
                      </span>
                    )}
                  </>
                )}
                {status === "completed" && "Completado"}
                {status === "error" && "Error"}
              </span>
            </div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {profiles.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setProfile(item.id)}
                  disabled={isBusy}
                  style={{
                    borderRadius: "999px",
                    padding: "0.35rem 0.95rem",
                    border: profile === item.id ? "1px solid #38bdf8" : "1px solid rgba(148,163,184,0.35)",
                    background: profile === item.id ? "rgba(56,189,248,0.18)" : "rgba(15,23,42,0.55)",
                    color: isBusy ? "rgba(148,163,184,0.75)" : "#e2e8f0",
                    cursor: isBusy ? "not-allowed" : "pointer",
                    transition: "all 0.2s ease",
                    opacity: isBusy && profile !== item.id ? 0.6 : 1,
                  }}
                >
                  <strong style={{ display: "block", fontSize: "0.85rem" }}>{item.label}</strong>
                  <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>{item.description}</span>
                </button>
              ))}
            </div>
          </header>

          <Uploader ref={uploaderRef} onSelect={handleSubmit} busy={isBusy} />
          {config?.max_upload_size_mb && (
            <span style={{ color: "#64748b", fontSize: "0.85rem" }}>
              Máximo {config.max_upload_size_mb} MB por archivo.
            </span>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              Idioma
              <select value={language} onChange={(event) => setLanguage(event.target.value)} disabled={isBusy}>
                {availableLanguages.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              Título (opcional)
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Reunión semanal"
                disabled={isBusy}
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              Etiquetas (opcional)
              <input
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="reunión, sprint, tareas"
                disabled={isBusy}
              />
            </label>
          </div>

          <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <input
                type="checkbox"
                checked={diarization}
                onChange={(event) => setDiarization(event.target.checked)}
                disabled={isBusy}
              />
              Diarización experimental
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <input
                type="checkbox"
                checked={wordTimestamps}
                onChange={(event) => setWordTimestamps(event.target.checked)}
                disabled={isBusy}
              />
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
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ color: status === "completed" ? "#22c55e" : "#fca5a5" }}>
                {status === "completed"
                  ? "Transcripción completada. Revisa y comparte el resultado con las acciones rápidas."
                  : error ?? "No se pudo completar la transcripción."}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
                {status === "completed" && (
                  <>
                    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", color: "#cbd5f5" }}>
                      Formato
                      <select value={downloadFormat} onChange={(event) => setDownloadFormat(event.target.value as TranscriptFormat)}>
                        <option value="txt">TXT</option>
                        <option value="md">Markdown</option>
                        <option value="srt">Subtítulos SRT</option>
                      </select>
                    </label>
                    <button
                      className="primary"
                      type="button"
                      disabled={downloading}
                      onClick={() => void handleQuickDownload(downloadFormat)}
                    >
                      {downloading ? "Preparando descarga…" : `Descargar ${downloadFormat.toUpperCase()}`}
                    </button>
                    <button
                      className="secondary"
                      type="button"
                      onClick={handleOpenTranscriptUrl}
                      disabled={!transcriptUrl}
                    >
                      Abrir enlace seguro
                    </button>
                    <button className="secondary" type="button" onClick={handleOpenLibrary}>
                      Ver en biblioteca
                    </button>
                  </>
                )}
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
