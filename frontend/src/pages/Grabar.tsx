import { useEffect, useRef, useState } from "react";
import { streamTranscription, uploadTranscription } from "@/lib/api";
import { AuthPanel } from "@/components/AuthPanel";
import { SseViewer } from "@/components/SseViewer";
import { useQualityProfiles } from "@/lib/hooks";

interface Props {
  onLibraryRefresh?: () => void;
}

export function GrabarPage({ onLibraryRefresh }: Props) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationRef = useRef<number>();
  const [level, setLevel] = useState(0);
  const [recording, setRecording] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [profile, setProfile] = useState("balanced");
  const [language, setLanguage] = useState("auto");
  const [tokens, setTokens] = useState<Array<{ text: string; t0: number; t1: number }>>([]);
  const [status, setStatus] = useState<"idle" | "recording" | "uploading" | "streaming" | "completed" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [title, setTitle] = useState("Grabación rápida");
  const stopStreamRef = useRef<() => void>();
  const { profiles } = useQualityProfiles();

  useEffect(() => () => {
    stopStreamRef.current?.();
    cancelAnimationFrame(animationRef.current ?? 0);
    audioContextRef.current?.close();
  }, []);

  useEffect(() => {
    if (profiles.length > 0 && !profiles.find((item) => item.id === profile)) {
      setProfile(profiles[0].id);
    }
  }, [profiles, profile]);

  function updateMeter() {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    const normalized = data.reduce((acc, value) => acc + Math.abs(value - 128), 0) / data.length;
    setLevel(Math.min(1, normalized / 128));
    animationRef.current = requestAnimationFrame(updateMeter);
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      updateMeter();

      const chunks: BlobPart[] = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      mediaRecorder.onstop = async () => {
        cancelAnimationFrame(animationRef.current ?? 0);
        analyser.disconnect();
        audioContext.close();
        const blob = new Blob(chunks, { type: "audio/webm" });
        const file = new File([blob], `grabacion-${Date.now()}.webm`, { type: "audio/webm" });
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
        await handleSubmit(file);
      };
      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setRecording(true);
      setTokens([]);
      setStatus("recording");
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo acceder al micrófono";
      setError(message);
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setRecording(false);
  }

  async function startStream(job: { job_id: string }) {
    setJobId(job.job_id);
    setStatus("streaming");
    stopStreamRef.current?.();
    stopStreamRef.current = streamTranscription(job.job_id, {
      onDelta(delta) {
        setTokens((prev) => [...prev, delta]);
      },
      onCompleted() {
        setStatus("completed");
        onLibraryRefresh?.();
      },
      onError(err) {
        setError(err.message);
        setStatus("error");
      },
    });
  }

  async function handleSubmit(file: File) {
    setStatus("uploading");
    setError(null);
    const formData = new FormData();
    formData.append("file", file);
    if (language !== "auto") formData.append("language", language);
    formData.append("profile", profile);
    formData.append("title", title || "Grabación rápida");
    try {
      const job = await uploadTranscription(formData);
      await startStream(job);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo enviar la grabación";
      setError(message);
      setStatus("error");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <section style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "2rem" }}>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <header>
            <h2 style={{ margin: 0 }}>Grabar desde el navegador</h2>
            <p style={{ margin: 0, color: "#94a3b8" }}>
              Controla el micro, visualiza niveles y envía la transcripción sin salir de la página.
            </p>
          </header>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              Idioma
              <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                <option value="auto">Automático</option>
                <option value="es">Español</option>
                <option value="en">Inglés</option>
                <option value="pt">Portugués</option>
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              Perfil de calidad
              <select value={profile} onChange={(event) => setProfile(event.target.value)}>
                {profiles.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.5rem", flex: 1 }}>
              Título
              <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Clases de audio" />
            </label>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "1rem",
              padding: "2rem",
              borderRadius: "24px",
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(148,163,184,0.2)",
            }}
          >
            <div
              style={{
                width: "100%",
                height: "12px",
                background: "rgba(148,163,184,0.2)",
                borderRadius: "999px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${Math.round(level * 100)}%`,
                  height: "100%",
                  background: "linear-gradient(90deg, #38bdf8 0%, #a855f7 100%)",
                  transition: "width 0.1s ease-out",
                }}
              />
            </div>
            <p style={{ margin: 0, color: "#94a3b8" }}>
              {recording ? "Grabando..." : "Pulsa grabar para comenzar"}
            </p>
            <div style={{ display: "flex", gap: "1rem" }}>
              <button
                className="primary"
                type="button"
                onClick={recording ? stopRecording : startRecording}
                style={{ paddingInline: "2.5rem" }}
              >
                {recording ? "Detener" : "Grabar"}
              </button>
              {audioUrl && (
                <audio controls src={audioUrl} style={{ borderRadius: "999px" }} />
              )}
            </div>
          </div>
          {error && <div style={{ color: "#fca5a5" }}>{error}</div>}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <AuthPanel onAuthenticated={onLibraryRefresh} onLogout={onLibraryRefresh} />
          <SseViewer tokens={tokens} status={status} error={error} onRetry={() => jobId && startStream({ job_id: jobId })} />
        </div>
      </section>
    </div>
  );
}
