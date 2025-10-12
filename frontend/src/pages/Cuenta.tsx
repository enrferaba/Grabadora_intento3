import { FormEvent, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { login, signup } from "@/lib/api";

type Step = "signup" | "login" | "guest";

interface Props {
  onAuthenticated?: () => void;
}

function FormWrapper({
  title,
  description,
  children,
  highlighted,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  highlighted?: boolean;
}) {
  return (
    <div
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        border: highlighted ? "1px solid rgba(56, 189, 248, 0.45)" : undefined,
        boxShadow: highlighted ? "0 12px 40px rgba(56, 189, 248, 0.15)" : undefined,
        minWidth: "280px",
      }}
    >
      <div>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <p style={{ margin: "0.35rem 0 0", color: "#94a3b8", fontSize: "0.95rem" }}>{description}</p>
      </div>
      {children}
    </div>
  );
}

export function CuentaPage({ onAuthenticated }: Props) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const focusStep = useMemo<Step>(() => {
    const mode = (searchParams.get("mode") ?? "").toLowerCase();
    if (mode === "login" || mode === "guest") return mode;
    return "signup";
  }, [searchParams]);

  const [signupEmail, setSignupEmail] = useState("usuario@ejemplo.com");
  const [signupPassword, setSignupPassword] = useState("supersegura");
  const [signupConfirm, setSignupConfirm] = useState("supersegura");
  const [signupBusy, setSignupBusy] = useState(false);
  const [signupError, setSignupError] = useState<string | null>(null);

  const [loginEmail, setLoginEmail] = useState("usuario@ejemplo.com");
  const [loginPassword, setLoginPassword] = useState("supersegura");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  async function handleSignup(event: FormEvent) {
    event.preventDefault();
    setSignupError(null);
    if (signupPassword !== signupConfirm) {
      setSignupError("Las contraseñas no coinciden");
      return;
    }
    setSignupBusy(true);
    try {
      await signup({ email: signupEmail, password: signupPassword });
      await login({ email: signupEmail, password: signupPassword });
      onAuthenticated?.();
      navigate("/transcribir", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo crear la cuenta";
      setSignupError(message);
    } finally {
      setSignupBusy(false);
    }
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setLoginError(null);
    setLoginBusy(true);
    try {
      await login({ email: loginEmail, password: loginPassword });
      onAuthenticated?.();
      navigate("/transcribir", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo iniciar sesión";
      setLoginError(message);
    } finally {
      setLoginBusy(false);
    }
  }

  function handleGuestAccess(event: FormEvent) {
    event.preventDefault();
    setSearchParams({ mode: "guest" });
    navigate("/transcribir");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <header style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <span style={{ color: "#38bdf8", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Tu espacio personal
        </span>
        <h1 style={{ margin: 0, fontSize: "2.5rem" }}>Gestiona tu cuenta y elige cómo quieres usar la plataforma</h1>
        <p style={{ color: "#94a3b8", fontSize: "1.05rem", maxWidth: "720px" }}>
          Puedes crear una cuenta para sincronizar transcripciones y métricas, iniciar sesión si ya tienes credenciales o
          continuar en modo invitado con cuota limitada. Elige la opción que mejor se adapte a tu momento.
        </p>
      </header>
      <section
        style={{
          display: "grid",
          gap: "2rem",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          alignItems: "start",
        }}
      >
        <FormWrapper
          title="Crear cuenta"
          description="Recibirás un enlace de verificación por correo."
          highlighted={focusStep === "signup"}
        >
          <form onSubmit={handleSignup} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              Correo electrónico
              <input
                type="email"
                value={signupEmail}
                onChange={(event) => setSignupEmail(event.target.value)}
                required
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              Contraseña
              <input
                type="password"
                value={signupPassword}
                onChange={(event) => setSignupPassword(event.target.value)}
                minLength={6}
                required
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              Confirmar contraseña
              <input
                type="password"
                value={signupConfirm}
                onChange={(event) => setSignupConfirm(event.target.value)}
                minLength={6}
                required
              />
            </label>
            {signupError && <div style={{ color: "#fca5a5" }}>{signupError}</div>}
            <button className="primary" type="submit" disabled={signupBusy}>
              {signupBusy ? "Creando cuenta..." : "Registrarme"}
            </button>
          </form>
        </FormWrapper>
        <FormWrapper
          title="Iniciar sesión"
          description="Guardamos tu token en este navegador para mantenerte conectado."
          highlighted={focusStep === "login"}
        >
          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              Correo electrónico
              <input
                type="email"
                value={loginEmail}
                onChange={(event) => setLoginEmail(event.target.value)}
                required
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              Contraseña
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                minLength={6}
                required
              />
            </label>
            {loginError && <div style={{ color: "#fca5a5" }}>{loginError}</div>}
            <button className="primary" type="submit" disabled={loginBusy}>
              {loginBusy ? "Accediendo..." : "Entrar"}
            </button>
          </form>
        </FormWrapper>
        <FormWrapper
          title="Usar sin cuenta"
          description="Prueba la transcripción con cuota gratuita. Las grabaciones se eliminan tras 24 horas."
          highlighted={focusStep === "guest"}
        >
          <form
            onSubmit={handleGuestAccess}
            style={{ display: "flex", flexDirection: "column", gap: "0.75rem", alignItems: "flex-start" }}
          >
            <p style={{ color: "#cbd5f5", margin: 0 }}>
              Podrás subir hasta 15 minutos diarios sin registro. Si luego creas una cuenta, conservaremos tus transcripciones
              recientes.
            </p>
            <button className="secondary" type="submit">
              Continuar como invitado
            </button>
            <small style={{ color: "#64748b" }}>
              Tip: puedes registrarte más adelante desde la Biblioteca si quieres conservar todo tu historial.
            </small>
          </form>
        </FormWrapper>
      </section>
    </div>
  );
}
