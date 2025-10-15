import { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useAppConfig, useQualityProfiles } from "@/lib/hooks";

const metricStyle: CSSProperties = {
  flex: "1 1 150px",
  background: "rgba(30, 41, 59, 0.65)",
  borderRadius: "20px",
  padding: "1rem 1.25rem",
  border: "1px solid rgba(148,163,184,0.15)",
};

const metricValueStyle: CSSProperties = {
  display: "block",
  fontSize: "1.8rem",
  fontWeight: 600,
};

const metricLabelStyle: CSSProperties = {
  color: "rgba(148,163,184,0.9)",
  fontSize: "0.9rem",
};

export function HeroBanner() {
  const navigate = useNavigate();
  const { profiles } = useQualityProfiles();
  const { config } = useAppConfig();

  const queueBackend = config?.queue_backend ?? "auto";
  const uploadLimit = config?.max_upload_size_mb ? `${config.max_upload_size_mb} MB` : "–";
  const storageMode = ((config?.features?.storage as { mode?: string } | undefined)?.mode ?? "automático").toString();

  return (
    <section className="hero">
      <div className="hero__content">
        <div className="hero__copy">
          <h1>Transcribe en vivo sin fricción</h1>
          <p>
            Arrastra tus audios o graba desde el navegador. La transcripción llega token a token mientras medimos progreso,
            latencia y calidad para ti.
          </p>
          <div className="hero__actions">
            <button className="primary" onClick={() => navigate("/cuenta?mode=login")}>Iniciar sesión</button>
            <button className="secondary" onClick={() => navigate("/transcribir")}>Probar sin cuenta</button>
          </div>
        </div>
        <div className="hero__preview">
          <div className="hero__preview-grid">
            {Array.from({ length: 12 }).map((_, index) => (
              <span
                key={index}
                style={{
                  display: "block",
                  background: "linear-gradient(180deg, rgba(226,232,240,0.9), rgba(59,130,246,0.5))",
                  borderRadius: "999px",
                  transform: `scaleY(${index % 3 === 0 ? 1 : 0.4})`,
                }}
              />
            ))}
          </div>
          <div className="hero__preview-caption">Deltas en vivo guardados en tu biblioteca</div>
        </div>
      </div>
      <div className="hero__metrics">
        <div style={metricStyle}>
          <span style={metricValueStyle}>{uploadLimit}</span>
          <span style={metricLabelStyle}>Límite de subida</span>
        </div>
        <div style={metricStyle}>
          <span style={metricValueStyle}>{queueBackend.toUpperCase()}</span>
          <span style={metricLabelStyle}>Cola en uso</span>
        </div>
        <div style={metricStyle}>
          <span style={metricValueStyle}>{storageMode === "remote" ? "S3" : "Local"}</span>
          <span style={metricLabelStyle}>Destino de archivos</span>
        </div>
      </div>
      <div className="hero__profiles">
        {profiles.map((item) => (
          <div key={item.id} className="hero__profile-card">
            <h4>{item.label}</h4>
            <p>{item.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
