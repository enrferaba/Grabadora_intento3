import { useMemo, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { BibliotecaPage } from "@/pages/Biblioteca";
import { GrabarPage } from "@/pages/Grabar";
import { TranscribirPage } from "@/pages/Transcribir";
import { getAuthState, logout, qualityProfiles } from "@/lib/api";

function Navigation() {
  const location = useLocation();
  const auth = getAuthState();
  const links = useMemo(
    () => [
      { to: "/transcribir", label: "Transcribir" },
      { to: "/grabar", label: "Grabar" },
      { to: "/biblioteca", label: "Biblioteca" },
    ],
    [],
  );

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1.5rem 2rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
        <Link to="/transcribir" style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
          Grabadora inteligente
        </Link>
        <div style={{ display: "flex", gap: "1rem" }}>
          {links.map((link) => {
            const active = location.pathname.startsWith(link.to);
            return (
              <Link
                key={link.to}
                to={link.to}
                style={{
                  color: active ? "#38bdf8" : "#cbd5f5",
                  fontWeight: active ? 600 : 500,
                  textDecoration: "none",
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>
      <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
        {auth ? (
          <>
            <span style={{ color: "#94a3b8", fontSize: "0.9rem" }}>{auth.email}</span>
            <button
              type="button"
              onClick={() => {
                logout();
                window.location.reload();
              }}
              style={{
                borderRadius: "999px",
                border: "1px solid rgba(148,163,184,0.35)",
                background: "transparent",
                color: "#cbd5f5",
                padding: "0.45rem 1.25rem",
                cursor: "pointer",
              }}
            >
              Cerrar sesión
            </button>
          </>
        ) : (
          <Link to="/transcribir" className="primary" style={{ textDecoration: "none" }}>
            Probar sin cuenta
          </Link>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  const [refreshToken, setRefreshToken] = useState(0);
  const handleRefresh = () => setRefreshToken((value) => value + 1);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      <Navigation />
      <main style={{ flex: 1, padding: "0 2rem 3rem 2rem", display: "flex", flexDirection: "column", gap: "3rem" }}>
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr",
            gap: "2rem",
            alignItems: "start",
          }}
        >
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h1 style={{ margin: 0 }}>Tu asistente de transcripción con SSE en vivo</h1>
            <p style={{ color: "#94a3b8", fontSize: "1.05rem" }}>
              Arrastra audio, graba desde el micro y guarda todo en una biblioteca inteligente con exportación a Markdown, SRT y
              conectores como Notion o Trello.
            </p>
            <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
              {qualityProfiles().map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: "1rem",
                    borderRadius: "16px",
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(148,163,184,0.25)",
                  }}
                >
                  <h4 style={{ margin: "0 0 0.25rem 0" }}>{item.title}</h4>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: "0.9rem" }}>{item.description}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h3 style={{ margin: 0 }}>¿Qué puedes hacer?</h3>
            <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "#cbd5f5", lineHeight: 1.7 }}>
              <li>Subir audio y recibir subtítulos token a token vía SSE.</li>
              <li>Grabar desde el navegador con monitor de volumen y reconexión automática.</li>
              <li>Organizar tu biblioteca con etiquetas, estados y exportaciones a TXT/MD/SRT.</li>
              <li>Compartir a herramientas externas como Notion o Trello.</li>
            </ul>
          </div>
        </section>
        <Routes>
          <Route path="/" element={<Navigate to="/transcribir" replace />} />
          <Route path="/transcribir" element={<TranscribirPage onLibraryRefresh={handleRefresh} />} />
          <Route path="/grabar" element={<GrabarPage onLibraryRefresh={handleRefresh} />} />
          <Route path="/biblioteca" element={<BibliotecaPage key={refreshToken} />} />
        </Routes>
      </main>
      <footer style={{ padding: "1.5rem 2rem", display: "flex", justifyContent: "space-between", color: "#94a3b8" }}>
        <span>© {new Date().getFullYear()} Grabadora Inteligente — Demo educativa lista para producto.</span>
        <div style={{ display: "flex", gap: "1rem" }}>
          <a href="/docs" style={{ color: "#38bdf8" }}>
            API Docs
          </a>
          <a href="/deploy/grafana/README.md" style={{ color: "#38bdf8" }}>
            Observabilidad
          </a>
        </div>
      </footer>
    </div>
  );
}
