import { useMemo, useState } from "react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import type { TranscriptSummary } from "@/lib/api";

interface TranscriptCardProps {
  transcript: TranscriptSummary;
  onOpen: (id: number) => void;
  onDownload: (id: number, format: TranscriptFormat) => void | Promise<void>;
  onExport: (id: number, destination: ExportDestination, format: TranscriptFormat) => void | Promise<void>;
  pendingAction?: "download" | "export" | null;
}

const STATUS_COLORS: Record<string, string> = {
  queued: "#fbbf24",
  transcribing: "#38bdf8",
  completed: "#22c55e",
  error: "#f87171",
};

type TranscriptFormat = "txt" | "md" | "srt";
type ExportDestination = "notion" | "trello" | "webhook";

const DESTINATION_LABELS: Record<ExportDestination, string> = {
  notion: "Notion",
  trello: "Trello",
  webhook: "Webhook",
};

function formatDuration(seconds?: number | null): string | null {
  if (!seconds || Number.isNaN(seconds) || seconds <= 0) return null;
  const rounded = Math.round(seconds);
  const minutes = Math.floor(rounded / 60);
  const secs = rounded % 60;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  }
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export function TranscriptCard({ transcript, onOpen, onDownload, onExport, pendingAction }: TranscriptCardProps) {
  const created = parseISO(transcript.created_at);
  const chips = transcript.tags?.length ? transcript.tags : [];
  const statusColor = STATUS_COLORS[transcript.status] ?? "#94a3b8";
  const [format, setFormat] = useState<TranscriptFormat>("txt");
  const [destination, setDestination] = useState<ExportDestination>("notion");
  const isCompleted = transcript.status === "completed";
  const durationLabel = useMemo(() => formatDuration(transcript.duration_seconds), [transcript.duration_seconds]);
  const runtimeLabel = useMemo(() => formatDuration(transcript.runtime_seconds), [transcript.runtime_seconds]);
  const formatLabel = format.toUpperCase();
  const destinationLabel = DESTINATION_LABELS[destination];
  const isDownloading = pendingAction === "download";
  const isExporting = pendingAction === "export";

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
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1.25rem", color: "#94a3b8", fontSize: "0.85rem" }}>
        {durationLabel && <span>Duración · {durationLabel}</span>}
        {runtimeLabel && <span>Proceso · {runtimeLabel}</span>}
        {transcript.quality_profile && <span>Perfil · {transcript.quality_profile}</span>}
        {transcript.language && <span>Idioma · {transcript.language}</span>}
      </div>
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
      <footer style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        <button className="secondary" type="button" onClick={() => onOpen(transcript.id)}>
          Ver detalle
        </button>
        <label style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          Formato
          <select value={format} onChange={(event) => setFormat(event.target.value as TranscriptFormat)} disabled={!isCompleted}>
            <option value="txt">TXT</option>
            <option value="md">Markdown</option>
            <option value="srt">Subtítulos SRT</option>
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          Destino
          <select
            value={destination}
            onChange={(event) => setDestination(event.target.value as ExportDestination)}
            disabled={!isCompleted}
          >
            <option value="notion">Notion</option>
            <option value="trello">Trello</option>
            <option value="webhook">Webhook</option>
          </select>
        </label>
        <button
          className="primary"
          type="button"
          disabled={!isCompleted || isDownloading}
          onClick={() => onDownload(transcript.id, format)}
        >
          {isDownloading ? "Descargando…" : `Descargar ${formatLabel}`}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => onExport(transcript.id, destination, format)}
          disabled={!isCompleted || isExporting}
        >
          {isExporting ? "Enviando…" : `Enviar a ${destinationLabel}`}
        </button>
      </footer>
    </article>
  );
}
