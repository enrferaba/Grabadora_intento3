import { NavLink, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import { getAuthState, logout } from "@/lib/api";

interface NavigationBarProps {
  onCloseMenu?: () => void;
}

export function NavigationBar({ onCloseMenu }: NavigationBarProps) {
  const navigate = useNavigate();
  const auth = getAuthState();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const links = useMemo(
    () => [
      { to: "/transcribir", label: "Transcribir" },
      { to: "/grabar", label: "Grabar" },
      { to: "/biblioteca", label: "Biblioteca" },
    ],
    [],
  );

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
        onCloseMenu?.();
      }
    }
    if (menuOpen) {
      document.addEventListener("click", handleOutsideClick);
    }
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [menuOpen, onCloseMenu]);

  function handleNavigate(path: string) {
    navigate(path);
    setMenuOpen(false);
    onCloseMenu?.();
  }

  function handleLogout() {
    logout();
    handleNavigate("/transcribir");
  }

  return (
    <nav className="navbar">
      <button type="button" className="navbar__brand" onClick={() => handleNavigate("/transcribir")}>Grabadora inteligente</button>
      <div className="navbar__links">
        {links.map((link) => (
          <NavLink key={link.to} to={link.to} className={({ isActive }) => (isActive ? "nav-link nav-link--active" : "nav-link")}>
            {link.label}
          </NavLink>
        ))}
      </div>
      <div className="navbar__account" ref={menuRef}>
        <button
          type="button"
          className="account-button"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((value) => !value)}
        >
          {auth ? auth.email.charAt(0).toUpperCase() : "👤"}
        </button>
        {menuOpen && (
          <div className="account-menu" role="menu">
            {auth ? (
              <>
                <div className="account-menu__header">{auth.email}</div>
                <button type="button" className="account-menu__item" onClick={() => handleNavigate("/cuenta")}>
                  Ver cuenta
                </button>
                <button type="button" className="account-menu__item" onClick={() => handleNavigate("/biblioteca")}>
                  Ir a mi biblioteca
                </button>
                <button type="button" className="account-menu__item account-menu__item--danger" onClick={handleLogout}>
                  Cerrar sesión
                </button>
              </>
            ) : (
              <>
                <button type="button" className="account-menu__item" onClick={() => handleNavigate("/cuenta?mode=signup")}>
                  Crear cuenta
                </button>
                <button type="button" className="account-menu__item" onClick={() => handleNavigate("/cuenta?mode=login")}>
                  Iniciar sesión
                </button>
                <button type="button" className="account-menu__item" onClick={() => handleNavigate("/transcribir")}>
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
