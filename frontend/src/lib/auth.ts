export interface AuthState {
  token: string;
  email: string;
}

const TOKEN_KEY = "grabadora.jwt";
const EMAIL_KEY = "grabadora.email";

export function getAuthState(): AuthState | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const email = localStorage.getItem(EMAIL_KEY) ?? "";
  if (!token) return null;
  return { token, email };
}

export function setAuthState(state: AuthState): void {
  localStorage.setItem(TOKEN_KEY, state.token);
  localStorage.setItem(EMAIL_KEY, state.email);
}

export function clearAuthState(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
}
