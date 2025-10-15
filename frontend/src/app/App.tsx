import { Navigate, Route, Routes } from "react-router-dom";
import { useCallback, useState } from "react";
import { AppShell } from "@/app/layout/AppShell";
import { TranscribePage } from "@/features/transcribe/TranscribePage";
import { RecordPage } from "@/features/record/RecordPage";
import { LibraryPage } from "@/features/library/LibraryPage";
import { AccountPage } from "@/features/account/AccountPage";

export default function App() {
  const [refreshToken, setRefreshToken] = useState(0);
  const handleRefresh = useCallback(() => setRefreshToken((value) => value + 1), []);

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/transcribir" replace />} />
        <Route path="/transcribir" element={<TranscribePage onLibraryRefresh={handleRefresh} />} />
        <Route path="/grabar" element={<RecordPage onLibraryRefresh={handleRefresh} />} />
        <Route path="/biblioteca" element={<LibraryPage key={refreshToken} />} />
        <Route path="/cuenta" element={<AccountPage onAuthenticated={handleRefresh} />} />
      </Route>
    </Routes>
  );
}
