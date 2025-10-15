import { useEffect, useState } from "react";
import type { TranscriptDetail, TranscriptSummary } from "@/lib/api";
import { downloadTranscript, exportTranscript, getTranscript, listTranscripts } from "@/lib/api";
import { TranscriptCard } from "@/features/library/components/TranscriptCard";
import { MessageBanner } from "@/components/MessageBanner";

type TranscriptFormat = "txt" | "md" | "srt";
type ExportDestination = "notion" | "trello" | "webhook";

export function LibraryPage() {
  const [items, setItems] = useState<TranscriptSummary[]>([]);
  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [pending, setPending] = useState<{ id: number; action: "download" | "export" } | null>(null);
  const [detailFormat, setDetailFormat] = useState<TranscriptFormat>("txt");
  const [detailDestination, setDetailDestination] = useState<ExportDestination>("notion");

  async function loadTranscripts() {
    try {
      setLoading(true);
      setError(null);
      const data = await listTranscripts({ search: search || undefined, status: status || undefined });
      setItems(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo cargar la biblioteca";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadTranscripts();
  }, []);

  useEffect(() => {
    const handle = setTimeout(() => {
      void loadTranscripts();
    }, 300);
    return () => clearTimeout(handle);
  }, [search, status]);

  async function openDetail(id: number) {
    try {
      const data = await getTranscript(id);
      setDetail(data);
      setDetailFormat("txt");
      setDetailDestination("notion");
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo abrir la transcripción";
      setError(message);
    }
  }

  async function handleDownload(id: number, format: TranscriptFormat) {
    try {
      setPending({ id, action: "download" });
      await downloadTranscript(id, format);
      setBanner({ tone: "success", message: `Descarga en formato ${format.toUpperCase()} preparada.` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo descargar la transcripción";
      setBanner({ tone: "error", message });
    } finally {
      setPending((previous) => (previous?.id === id ? null : previous));
    }
  }

  async function handleExport(id: number, destination: ExportDestination, format: TranscriptFormat) {
    try {
      setPending({ id, action: "export" });
      await exportTranscript(id, destination, format);
      setBanner({
        tone: "success",
        message: `Transcripción enviada a ${destination === "webhook" ? "tu webhook" : destination}.`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo exportar la transcripción";
      setBanner({ tone: "error", message });
    } finally {
      setPending((previous) => (previous?.id === id ? null : previous));
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: "2rem", alignItems: "start" }}>
      <section style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <header>
            <h2 style={{ margin: 0 }}>Biblioteca</h2>
            <p style={{ margin: 0, color: "#94a3b8" }}>
              Busca, etiqueta y exporta tus transcripciones. Cada registro muestra estado, perfil y duración.
            </p>
          </header>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar por título, idioma o etiqueta"
              style={{ flex: 1 }}
            />
            <select value={status} onChange={(event) => setStatus(event.target.value)} style={{ minWidth: "160px" }}>
              <option value="">Todos los estados</option>
              <option value="queued">En cola</option>
              <option value="transcribing">Procesando</option>
              <option value="completed">Completado</option>
              <option value="error">Error</option>
            </select>
            <button className="primary" type="button" onClick={() => void loadTranscripts()}>
              Actualizar
            </button>
          </div>
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
        </div>
        <div style={{ display: "grid", gap: "1rem" }}>
          {loading && <p style={{ color: "#94a3b8" }}>Cargando...</p>}
          {!loading && items.length === 0 && <p style={{ color: "#64748b" }}>Aún no hay transcripciones guardadas.</p>}
          {items.map((item) => (
            <TranscriptCard
              key={item.id}
              transcript={item}
              onOpen={openDetail}
              onDownload={(id, format) => void handleDownload(id, format)}
              onExport={(id, destination, format) => void handleExport(id, destination, format)}
              pendingAction={pending?.id === item.id ? pending.action : null}
            />
          ))}
        </div>
      </section>
      <aside className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem", minHeight: "320px" }}>
        <header>
          <h3 style={{ margin: 0 }}>Detalle</h3>
          <p style={{ margin: 0, color: "#94a3b8" }}>
            Selecciona una transcripción para ver segmentos, descargas y acciones rápidas.
          </p>
        </header>
        {detail ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <h4 style={{ margin: "0 0 0.5rem 0" }}>{detail.title || "Transcripción"}</h4>
              <p style={{ margin: 0, color: "#94a3b8" }}>
                Idioma: {detail.language || "desconocido"} · Perfil: {detail.quality_profile || "n/a"}
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                Formato
                <select value={detailFormat} onChange={(event) => setDetailFormat(event.target.value as TranscriptFormat)}>
                  <option value="txt">TXT</option>
                  <option value="md">Markdown</option>
                  <option value="srt">SRT</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                Destino
                <select
                  value={detailDestination}
                  onChange={(event) => setDetailDestination(event.target.value as ExportDestination)}
                >
                  <option value="notion">Notion</option>
                  <option value="trello">Trello</option>
                  <option value="webhook">Webhook</option>
                </select>
              </label>
              <button
                className="primary"
                type="button"
                disabled={pending?.id === detail.id && pending.action === "download"}
                onClick={() => void handleDownload(detail.id, detailFormat)}
              >
                {pending?.id === detail.id && pending.action === "download" ? "Preparando…" : "Descargar"}
              </button>
              <button
                className="secondary"
                type="button"
                disabled={pending?.id === detail.id && pending.action === "export"}
                onClick={() => void handleExport(detail.id, detailDestination, detailFormat)}
              >
                {pending?.id === detail.id && pending.action === "export" ? "Enviando…" : "Exportar"}
              </button>
              {detail.transcript_url && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => window.open(detail.transcript_url as string, "_blank", "noopener")}
                >
                  Abrir enlace seguro
                </button>
              )}
            </div>
            <div
              style={{
                maxHeight: "280px",
                overflowY: "auto",
                padding: "1rem",
                borderRadius: "16px",
                background: "rgba(2,6,23,0.45)",
                border: "1px solid rgba(148,163,184,0.2)",
              }}
            >
              {detail.segments.length === 0 && <p style={{ color: "#64748b" }}>Aún no hay segmentos disponibles.</p>}
              {detail.segments.map((segment, index) => (
                <div key={`${segment.start}-${index}`} style={{ marginBottom: "0.75rem" }}>
                  <p style={{ margin: 0, fontSize: "0.75rem", color: "#94a3b8" }}>
                    {segment.start.toFixed(2)}s → {segment.end.toFixed(2)}s
                  </p>
                  <p style={{ margin: 0 }}>{segment.text}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p style={{ color: "#64748b" }}>Selecciona una transcripción a la izquierda para ver los detalles.</p>
        )}
      </aside>
    </div>
  );
}
