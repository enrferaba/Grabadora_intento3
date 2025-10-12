import { Navigate, Route, Routes } from "react-router-dom";
import { useCallback, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { TranscribirPage } from "@/pages/Transcribir";
import { GrabarPage } from "@/pages/Grabar";
import { BibliotecaPage } from "@/pages/Biblioteca";
import { CuentaPage } from "@/pages/Cuenta";

export default function App() {
  const [refreshToken, setRefreshToken] = useState(0);
  const handleRefresh = useCallback(() => setRefreshToken((value) => value + 1), []);

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/transcribir" replace />} />
        <Route path="/transcribir" element={<TranscribirPage onLibraryRefresh={handleRefresh} />} />
        <Route path="/grabar" element={<GrabarPage onLibraryRefresh={handleRefresh} />} />
        <Route path="/biblioteca" element={<BibliotecaPage key={refreshToken} />} />
        <Route path="/cuenta" element={<CuentaPage onAuthenticated={handleRefresh} />} />
      </Route>
    </Routes>
  );
}
