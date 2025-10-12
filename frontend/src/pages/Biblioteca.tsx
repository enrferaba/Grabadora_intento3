import { useEffect, useState } from "react";
import type { TranscriptDetail, TranscriptSummary } from "@/lib/api";
import { downloadTranscript, exportTranscript, getTranscript, listTranscripts } from "@/lib/api";
import { TranscriptCard } from "@/components/TranscriptCard";

export function BibliotecaPage() {
  const [items, setItems] = useState<TranscriptSummary[]>([]);
  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    loadTranscripts();
  }, []);

  useEffect(() => {
    const handle = setTimeout(() => {
      loadTranscripts();
    }, 300);
    return () => clearTimeout(handle);
  }, [search, status]);

  async function openDetail(id: number) {
    try {
      const data = await getTranscript(id);
      setDetail(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo abrir la transcripción";
      setError(message);
    }
  }

  async function handleExport(id: number, destination: "notion" | "trello") {
    await exportTranscript(id, destination);
    alert(`Transcripción enviada a ${destination}`);
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
            <button className="primary" type="button" onClick={loadTranscripts}>
              Actualizar
            </button>
          </div>
          {error && <div style={{ color: "#fca5a5" }}>{error}</div>}
        </div>
        <div style={{ display: "grid", gap: "1rem" }}>
          {loading && <p style={{ color: "#94a3b8" }}>Cargando...</p>}
          {!loading && items.length === 0 && <p style={{ color: "#64748b" }}>Aún no hay transcripciones guardadas.</p>}
          {items.map((item) => (
            <TranscriptCard
              key={item.id}
              transcript={item}
              onOpen={openDetail}
              onExport={(id) => handleExport(id, "notion")}
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
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <button className="primary" type="button" onClick={() => downloadTranscript(detail.id, "txt")}>TXT</button>
              <button className="primary" type="button" onClick={() => downloadTranscript(detail.id, "md")}>Markdown</button>
              <button className="primary" type="button" onClick={() => downloadTranscript(detail.id, "srt")}>SRT</button>
              <button
                type="button"
                onClick={() => handleExport(detail.id, "trello")}
                style={{
                  borderRadius: "999px",
                  border: "1px solid rgba(148,163,184,0.35)",
                  background: "transparent",
                  color: "#cbd5f5",
                  padding: "0.5rem 1.2rem",
                  cursor: "pointer",
                }}
              >
                Enviar a Trello
              </button>
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
