import { formatDistanceToNow, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import type { TranscriptSummary } from "@/lib/api";

interface TranscriptCardProps {
  transcript: TranscriptSummary;
  onOpen: (id: number) => void;
  onExport: (id: number) => void;
}

const STATUS_COLORS: Record<string, string> = {
  queued: "#fbbf24",
  transcribing: "#38bdf8",
  completed: "#22c55e",
  error: "#f87171",
};

export function TranscriptCard({ transcript, onOpen, onExport }: TranscriptCardProps) {
  const created = parseISO(transcript.created_at);
  const chips = transcript.tags?.length ? transcript.tags : [];
  const statusColor = STATUS_COLORS[transcript.status] ?? "#94a3b8";
  return (
    <article
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        width: "100%",
      }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "1rem" }}>
        <div>
          <h3 style={{ margin: 0 }}>{transcript.title || "Transcripción sin título"}</h3>
          <p style={{ margin: 0, color: "#94a3b8" }}>
            {formatDistanceToNow(created, { addSuffix: true, locale: es })}
          </p>
        </div>
        <span
          style={{
            padding: "0.25rem 0.75rem",
            borderRadius: "999px",
            background: `${statusColor}33`,
            color: statusColor,
            fontSize: "0.85rem",
            textTransform: "capitalize",
          }}
        >
          {transcript.status}
        </span>
      </header>
      {chips.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {chips.map((tag) => (
            <span
              key={tag}
              style={{
                padding: "0.2rem 0.65rem",
                borderRadius: "999px",
                background: "rgba(56, 189, 248, 0.12)",
                color: "#38bdf8",
                fontSize: "0.75rem",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      <footer style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
        <button
          type="button"
          onClick={() => onExport(transcript.id)}
          style={{
            borderRadius: "999px",
            border: "1px solid rgba(148,163,184,0.35)",
            background: "transparent",
            color: "#cbd5f5",
            padding: "0.5rem 1.25rem",
            cursor: "pointer",
          }}
        >
          Enviar a...
        </button>
        <button className="primary" type="button" onClick={() => onOpen(transcript.id)}>
          Abrir
        </button>
      </footer>
    </article>
  );
}
