import { Outlet, useLocation } from "react-router-dom";
import { NavigationBar } from "./NavigationBar";
import { Footer } from "./Footer";

export function AppShell() {
  const location = useLocation();

  return (
    <div className="app-shell">
      <NavigationBar />
      <main className="app-main">
        <div className="app-main__content">
          <Outlet />
        </div>
      </main>
      <Footer />
    </div>
  );
}
