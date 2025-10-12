import { Outlet, useLocation } from "react-router-dom";
import { NavigationBar } from "./NavigationBar";
import { Footer } from "./Footer";
import { HeroBanner } from "@/components/home/HeroBanner";

export function AppShell() {
  const location = useLocation();
  const showHero = location.pathname === "/transcribir";

  return (
    <div className="app-shell">
      <NavigationBar />
      <main className="app-main">
        {showHero && <HeroBanner />}
        <div className="app-main__content">
          <Outlet />
        </div>
      </main>
      <Footer />
    </div>
  );
}
