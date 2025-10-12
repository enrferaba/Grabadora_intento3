import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { BibliotecaPage } from "@/pages/Biblioteca";
import { GrabarPage } from "@/pages/Grabar";
import { TranscribirPage } from "@/pages/Transcribir";
import { CuentaPage } from "@/pages/Cuenta";
import { getAuthState, logout, qualityProfiles } from "@/lib/api";

function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const auth = getAuthState();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const links = useMemo(
    () => [
      { to: "/transcribir", label: "Transcribir" },
      { to: "/grabar", label: "Grabar" },
      { to: "/biblioteca", label: "Biblioteca" },
      { to: "/cuenta", label: "Cuenta" },
    ],
    [],
  );

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("click", handleClick);
    }
    return () => document.removeEventListener("click", handleClick);
  }, [menuOpen]);

  function handleNavigate(path: string) {
    navigate(path);
    setMenuOpen(false);
  }

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
                  color: active ? "#0f172a" : "#cbd5f5",
                  fontWeight: 600,
                  textDecoration: "none",
                  background: active ? "linear-gradient(135deg, #38bdf8 0%, #a855f7 100%)" : "rgba(15, 23, 42, 0.7)",
                  border: active ? "none" : "1px solid rgba(148,163,184,0.35)",
                  borderRadius: "999px",
                  padding: "0.55rem 1.25rem",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>
      <div style={{ position: "relative" }} ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen((value) => !value)}
          style={{
            width: "44px",
            height: "44px",
            borderRadius: "999px",
            border: "1px solid rgba(148,163,184,0.45)",
            background: "rgba(15,23,42,0.75)",
            color: "#38bdf8",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "1.1rem",
            cursor: "pointer",
          }}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
        >
          {auth ? auth.email.charAt(0).toUpperCase() : "👤"}
        </button>
        {menuOpen && (
          <div
            style={{
              position: "absolute",
              right: 0,
              marginTop: "0.75rem",
              minWidth: "220px",
              background: "rgba(15, 23, 42, 0.95)",
              borderRadius: "16px",
              border: "1px solid rgba(148,163,184,0.25)",
              boxShadow: "0 18px 40px rgba(15, 23, 42, 0.45)",
              padding: "0.75rem",
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem",
              zIndex: 20,
            }}
            role="menu"
          >
            {auth ? (
              <>
                <div style={{ color: "#cbd5f5", fontWeight: 600 }}>{auth.email}</div>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#38bdf8",
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "0.25rem 0",
                  }}
                  onClick={() => handleNavigate("/cuenta")}
                >
                  Ver cuenta
                </button>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#38bdf8",
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "0.25rem 0",
                  }}
                  onClick={() => handleNavigate("/biblioteca")}
                >
                  Ir a mi biblioteca
                </button>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#fca5a5",
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "0.25rem 0",
                  }}
                  onClick={() => {
                    logout();
                    handleNavigate("/transcribir");
                  }}
                >
                  Cerrar sesión
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#38bdf8",
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "0.25rem 0",
                  }}
                  onClick={() => handleNavigate("/cuenta?mode=signup")}
                >
                  Crear cuenta
                </button>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#38bdf8",
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "0.25rem 0",
                  }}
                  onClick={() => handleNavigate("/cuenta?mode=login")}
                >
                  Iniciar sesión
                </button>
                <button
                  type="button"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#cbd5f5",
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "0.25rem 0",
                  }}
                  onClick={() => handleNavigate("/transcribir")}
                >
                  Usar sin cuenta
                </button>
              </>
            )}
          </div>
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
          <Route path="/cuenta" element={<CuentaPage onAuthenticated={handleRefresh} />} />
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
