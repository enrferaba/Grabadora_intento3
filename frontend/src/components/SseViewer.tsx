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
}

export function SseViewer({ tokens, status, error, onRetry }: SseViewerProps) {
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

  return (
    <div className="card" style={{ width: "100%", minHeight: "280px", display: "flex", flexDirection: "column", gap: "1rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0 }}>Deltas en vivo</h3>
          <p style={{ margin: 0, color: "#94a3b8" }}>{statusCopy[status]}</p>
        </div>
        {status === "error" && onRetry && (
          <button className="primary" type="button" onClick={onRetry}>
            Reintentar
          </button>
        )}
      </header>
      <div
        ref={containerRef}
        style={{
          flex: 1,
          background: "rgba(2, 6, 23, 0.45)",
          borderRadius: "16px",
          padding: "1rem",
          overflowY: "auto",
          lineHeight: 1.6,
          fontSize: "1rem",
          color: "#f8fafc",
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
  );
}
