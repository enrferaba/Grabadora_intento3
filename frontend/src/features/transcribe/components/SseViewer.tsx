import { useEffect, useRef } from "react";

interface DeltaToken {
  text: string;
  t0: number;
  t1: number;
}

interface SseViewerProps {
  tokens: DeltaToken[];
  status: "idle" | "recording" | "uploading" | "streaming" | "completed" | "error";
  error?: string | null;
  onRetry?: () => void;
  fontSize: number;
  onFontSizeChange: (size: number) => void;
  fullscreen: boolean;
  onToggleFullscreen: () => void;
}

export function SseViewer({ tokens, status, error, onRetry, fontSize, onFontSizeChange, fullscreen, onToggleFullscreen }: SseViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [tokens]);

  const statusCopy: Record<SseViewerProps["status"], string> = {
    idle: "Listo para empezar",
    recording: "Grabando audio...",
    uploading: "Subiendo audio...",
    streaming: "Transcribiendo en vivo...",
    completed: "Transcripción completada",
    error: "Se produjo un error",
  };

  const clampedFontSize = Math.min(Math.max(fontSize, 0.8), 2.4);

  return (
    <div
      style={
        fullscreen
          ? {
              position: "fixed",
              inset: 0,
              zIndex: 40,
              padding: "2rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(15, 23, 42, 0.92)",
            }
          : { width: "100%" }
      }
    >
      <div
        className="card"
        style={{
          width: fullscreen ? "min(1100px, 92vw)" : "100%",
          minHeight: fullscreen ? "85vh" : "360px",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          background: "linear-gradient(180deg, rgba(15,23,42,0.92), rgba(7,37,67,0.92))",
          border: "1px solid rgba(56,189,248,0.15)",
          boxShadow: fullscreen
            ? "0 45px 90px -45px rgba(8,47,73,0.95)"
            : "0 30px 80px -50px rgba(8,47,73,0.9)",
        }}
      >
        <header style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1.4rem" }}>Transcripción en vivo</h3>
            <p style={{ margin: 0, color: "#94a3b8" }}>{statusCopy[status]}</p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button
              type="button"
              onClick={() => onFontSizeChange(clampedFontSize - 0.1)}
              style={{
                borderRadius: "10px",
                padding: "0.4rem 0.65rem",
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(148,163,184,0.35)",
                color: "#e2e8f0",
              }}
            >
              A-
            </button>
            <button
              type="button"
              onClick={() => onFontSizeChange(clampedFontSize + 0.1)}
              style={{
                borderRadius: "10px",
                padding: "0.4rem 0.65rem",
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(148,163,184,0.35)",
                color: "#e2e8f0",
              }}
            >
              A+
            </button>
            <button
              className="secondary"
              type="button"
              onClick={onToggleFullscreen}
              style={{
                padding: "0.45rem 0.9rem",
              }}
            >
              {fullscreen ? "Salir" : "Pantalla completa"}
            </button>
            {status === "error" && onRetry && (
              <button className="primary" type="button" onClick={onRetry}>
                Reintentar
              </button>
            )}
          </div>
        </header>
        <div
          ref={containerRef}
          style={{
            flex: 1,
            background: "rgba(2, 6, 23, 0.6)",
            borderRadius: "18px",
            padding: "1.25rem",
            overflowY: "auto",
            maxHeight: fullscreen ? "100%" : "460px",
            lineHeight: 1.6,
            fontSize: `${clampedFontSize}rem`,
            color: "#f8fafc",
            boxShadow: "inset 0 0 0 1px rgba(148,163,184,0.15)",
          }}
        >
          {tokens.length === 0 && status === "idle" && (
            <p style={{ color: "#64748b" }}>Los fragmentos aparecerán aquí en cuanto empiece la transcripción.</p>
          )}
          {tokens.length > 0 && (
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {tokens.map((token, index) => (
                <span key={`${token.t0}-${index}`} style={{ opacity: index === tokens.length - 1 ? 1 : 0.9 }}>
                  {token.text}
                </span>
              ))}
            </p>
          )}
          {error && <p style={{ color: "#fca5a5" }}>{error}</p>}
        </div>
      </div>
    </div>
  );
}
