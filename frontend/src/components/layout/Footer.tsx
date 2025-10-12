export function Footer() {
  return (
    <footer className="app-footer">
      <span>© {new Date().getFullYear()} Grabadora Inteligente — Demo educativa lista para producto.</span>
      <div className="app-footer__links">
        <a href="/docs">API Docs</a>
        <a href="/deploy/grafana/README.md">Observabilidad</a>
      </div>
    </footer>
  );
}
