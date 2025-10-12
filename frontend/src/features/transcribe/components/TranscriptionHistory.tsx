import { useEffect, useMemo, useState } from "react";
import { downloadTranscript, listTranscripts, type TranscriptSummary } from "@/lib/api";
import { MessageBanner } from "@/components/MessageBanner";

interface Props {
  refreshKey?: number;
  onSelect?: (transcript: TranscriptSummary) => void;
}

const statusColors: Record<string, string> = {
  queued: "rgba(148,163,184,0.35)",
  transcribing: "rgba(59,130,246,0.55)",
  completed: "rgba(34,197,94,0.65)",
  error: "rgba(239,68,68,0.65)",
};

type TranscriptFormat = "txt" | "md" | "srt";

function formatDate(value: string | null | undefined): string {
  if (!value) return "–";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "–";
  }
  return date.toLocaleString(undefined, { hour12: false });
}

export function TranscriptionHistory({ refreshKey = 0, onSelect }: Props) {
  const [items, setItems] = useState<TranscriptSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [formatSelection, setFormatSelection] = useState<Record<number, TranscriptFormat>>({});

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const data = await listTranscripts();
        if (!active) return;
        setItems(data);
        setError(null);
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : "No se pudo cargar el historial";
        setError(message);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [refreshKey]);

  const emptyState = useMemo(() => !loading && items.length === 0, [items.length, loading]);

  useEffect(() => {
    if (!banner) return;
    const timer = window.setTimeout(() => setBanner(null), 4000);
    return () => window.clearTimeout(timer);
  }, [banner]);

  async function handleDownload(id: number, format: TranscriptFormat) {
    try {
      setDownloadingId(id);
      await downloadTranscript(id, format);
      setBanner({ tone: "success", message: `Descarga en formato ${format.toUpperCase()} preparada.` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo descargar la transcripción";
      setBanner({ tone: "error", message });
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <section
      className="card"
      style={{ display: "flex", flexDirection: "column", gap: "1.5rem", padding: "1.75rem" }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0 }}>Historial de transcripciones</h3>
          <p style={{ margin: 0, color: "#94a3b8" }}>
            Consulta el progreso y descarga los resultados cuando estén listos.
          </p>
        </div>
        {loading && <span style={{ color: "#38bdf8" }}>Actualizando…</span>}
      </header>

      {error && (
        <MessageBanner tone="error" onClose={() => setError(null)}>
          {error}
        </MessageBanner>
      )}
      {banner && (
        <MessageBanner tone={banner.tone} onClose={() => setBanner(null)}>
          {banner.message}
        </MessageBanner>
      )}

      {emptyState ? (
        <div
          style={{
            padding: "2rem",
            borderRadius: "16px",
            background: "rgba(15,23,42,0.55)",
            textAlign: "center",
            color: "#94a3b8",
          }}
        >
          Sube tu primer audio para verlo aquí.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              minWidth: "640px",
            }}
          >
            <thead>
              <tr style={{ textAlign: "left", color: "#64748b", fontSize: "0.8rem", letterSpacing: "0.06em" }}>
                <th style={{ padding: "0.5rem 0.75rem" }}>Título</th>
                <th style={{ padding: "0.5rem 0.75rem" }}>Estado</th>
                <th style={{ padding: "0.5rem 0.75rem" }}>Idioma</th>
                <th style={{ padding: "0.5rem 0.75rem" }}>Perfil</th>
                <th style={{ padding: "0.5rem 0.75rem" }}>Actualizado</th>
                <th style={{ padding: "0.5rem 0.75rem" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const color = statusColors[item.status] ?? "rgba(148,163,184,0.35)";
                return (
                  <tr key={item.id} style={{ borderTop: "1px solid rgba(148,163,184,0.15)" }}>
                    <td style={{ padding: "0.75rem", color: "#e2e8f0", fontWeight: 500 }}>
                      {item.title || `Audio ${item.job_id.slice(0, 8)}`}
                      {item.tags.length > 0 && (
                        <div style={{ marginTop: "0.3rem", color: "#64748b", fontSize: "0.8rem" }}>
                          {item.tags.join(", ")}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "0.75rem" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          padding: "0.25rem 0.6rem",
                          borderRadius: "999px",
                          background: color,
                          color: "#0f172a",
                          fontWeight: 600,
                          fontSize: "0.75rem",
                          textTransform: "capitalize",
                        }}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td style={{ padding: "0.75rem", color: "#cbd5f5" }}>{item.language || "auto"}</td>
                    <td style={{ padding: "0.75rem", color: "#cbd5f5" }}>{item.quality_profile || "–"}</td>
                    <td style={{ padding: "0.75rem", color: "#cbd5f5" }}>{formatDate(item.updated_at)}</td>
                    <td style={{ padding: "0.75rem" }}>
                      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                        <button
                          className="secondary"
                          type="button"
                          onClick={() => onSelect?.(item)}
                          style={{ padding: "0.35rem 0.75rem" }}
                        >
                          Ver
                        </button>
                        <select
                          value={formatSelection[item.id] ?? "txt"}
                          onChange={(event) =>
                            setFormatSelection((prev) => ({ ...prev, [item.id]: event.target.value as TranscriptFormat }))
                          }
                          style={{ minWidth: "120px" }}
                          disabled={item.status !== "completed"}
                        >
                          <option value="txt">TXT</option>
                          <option value="md">Markdown</option>
                          <option value="srt">SRT</option>
                        </select>
                        <button
                          className="primary"
                          type="button"
                          disabled={item.status !== "completed" || downloadingId === item.id}
                          onClick={() =>
                            void handleDownload(item.id, (formatSelection[item.id] ?? "txt") as TranscriptFormat)
                          }
                          style={{ padding: "0.35rem 0.75rem" }}
                        >
                          {downloadingId === item.id ? "Preparando…" : "Descargar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
