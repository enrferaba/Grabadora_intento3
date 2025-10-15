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
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = node;
      const distance = scrollHeight - (scrollTop + clientHeight);
      stickToBottomRef.current = distance <= 48;
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      node.removeEventListener("scroll", onScroll);
    };
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    if (!stickToBottomRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [tokens]);

  useEffect(() => {
    if (status === "idle") {
      stickToBottomRef.current = true;
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }
  }, [status]);

  const statusCopy: Record<SseViewerProps["status"], string> = {
    idle: "Listo para empezar",
    recording: "Grabando audio...",
    uploading: "Subiendo audio...",
    streaming: "Transcribiendo en vivo...",
    completed: "Transcripción completada",
    error: "Se produjo un error",
  };

  return (
    <div
      className="card"
      style={{
        width: "100%",
        minHeight: "360px",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        background: "linear-gradient(180deg, rgba(15,23,42,0.9), rgba(8,47,73,0.9))",
        border: "1px solid rgba(56,189,248,0.15)",
        boxShadow: "0 30px 80px -50px rgba(8,47,73,0.9)",
      }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "1.4rem" }}>Transcripción en vivo</h3>
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
          background: "rgba(2, 6, 23, 0.55)",
          borderRadius: "18px",
          padding: "1rem",
          overflowY: "auto",
          maxHeight: "440px",
          lineHeight: 1.6,
          fontSize: "1rem",
          color: "#f8fafc",
          boxShadow: "inset 0 0 0 1px rgba(148,163,184,0.1)",
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
