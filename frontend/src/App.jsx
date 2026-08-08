import { useEffect, useState } from "react";
import { SessionContext } from "./context/SessionContext";
import { setAuthSession, setUnauthorizedHandler } from "./api/client";
import LoginAdmin from "./features/vehiculos/LoginAdmin";
import VehiculosAdminPage from "./features/vehiculos/VehiculosAdminPage";

/**
 * Raíz de la app. Mantiene la sesión del admin (`{ username, password } |
 * null`) en memoria vía `useState` — nunca en localStorage/sessionStorage
 * (AGENTS.md, threat model FEAT-001a). Sin sesión, se muestra `LoginAdmin`;
 * con sesión, `VehiculosAdminPage`. Sincroniza la sesión con `client.js`
 * (que la usa para el header `Authorization` de cada request) y registra el
 * handler que limpia la sesión cuando el backend responde 401.
 */
export default function App() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    setAuthSession(session);
  }, [session]);

  useEffect(() => {
    setUnauthorizedHandler(() => setSession(null));
  }, []);

  return (
    <SessionContext.Provider value={{ session, setSession }}>
      {session ? <VehiculosAdminPage /> : <LoginAdmin />}
    </SessionContext.Provider>
  );
}
