import { useState } from "react";
import { getAuthState, login, logout, signup } from "@/lib/api";

interface AuthPanelProps {
  onAuthenticated?: (email: string) => void;
  onLogout?: () => void;
}

export function AuthPanel({ onAuthenticated, onLogout }: AuthPanelProps) {
  const existing = getAuthState();
  const [mode, setMode] = useState<"login" | "signup">(existing ? "login" : "signup");
  const [email, setEmail] = useState(existing?.email ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signup") {
        if (password !== confirm) {
          throw new Error("Las contraseñas no coinciden");
        }
        await signup({ email, password });
        await login({ email, password });
      } else {
        await login({ email, password });
      }
      onAuthenticated?.(email);
      setPassword("");
      setConfirm("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo iniciar sesión";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    logout();
    onLogout?.();
  }

  if (existing && !busy) {
    return (
      <div className="card" style={{ minWidth: "280px" }}>
        <h3 style={{ marginTop: 0 }}>Sesión iniciada</h3>
        <p style={{ marginBottom: "1rem", color: "#94a3b8" }}>Conectado como {existing.email}</p>
        <button className="primary" onClick={handleLogout}>Cerrar sesión</button>
      </div>
    );
  }

  return (
    <form className="card" onSubmit={handleSubmit} style={{ minWidth: "280px" }}>
      <h3 style={{ marginTop: 0 }}>{mode === "login" ? "Accede a tu cuenta" : "Crea una cuenta"}</h3>
      <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginBottom: "0.75rem" }}>
        Correo electrónico
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginBottom: "0.75rem" }}>
        Contraseña
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={6} />
      </label>
      {mode === "signup" && (
        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginBottom: "0.75rem" }}>
          Confirmar contraseña
          <input type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} required minLength={6} />
        </label>
      )}
      {error && <div style={{ color: "#fca5a5", marginBottom: "0.75rem" }}>{error}</div>}
      <button className="primary" type="submit" disabled={busy}>
        {busy ? "Procesando..." : mode === "login" ? "Entrar" : "Crear cuenta"}
      </button>
      <p style={{ marginTop: "1rem", fontSize: "0.85rem", color: "#cbd5f5" }}>
        {mode === "login" ? "¿No tienes cuenta?" : "¿Ya tienes cuenta?"}
        <button
          type="button"
          onClick={() => setMode((prev) => (prev === "login" ? "signup" : "login"))}
          style={{
            marginLeft: "0.35rem",
            background: "none",
            border: "none",
            color: "#38bdf8",
            cursor: "pointer",
            textDecoration: "underline",
          }}
        >
          {mode === "login" ? "Regístrate" : "Inicia sesión"}
        </button>
      </p>
    </form>
  );
}
