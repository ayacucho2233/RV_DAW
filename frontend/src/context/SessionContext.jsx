import { createContext, useContext } from "react";

/**
 * Contexto de sesión del admin. El valor es `{ session, setSession }`, donde
 * `session` es `{ username, password } | null`, guardado exclusivamente en
 * memoria (useState de `App.jsx`) — nunca en localStorage/sessionStorage
 * (prohibición explícita de AGENTS.md y del threat model de FEAT-001a).
 */
export const SessionContext = createContext(null);

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession debe usarse dentro de <SessionContext.Provider>");
  }
  return ctx;
}
