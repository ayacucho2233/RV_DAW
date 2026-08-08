import { useEffect, useState } from "react";
import { SessionContext } from "./context/SessionContext";
import { setAuthSession, setUnauthorizedHandler } from "./api/client";
import LoginAdmin from "./features/vehiculos/LoginAdmin";
import VehiculosAdminPage from "./features/vehiculos/VehiculosAdminPage";
import ReservasPublicPage from "./features/reservas/ReservasPublicPage";
import ReservasListado from "./features/reservas/ReservasListado";

/**
 * Raíz de la app. Mantiene la sesión del admin (`{ username, password } |
 * null`) en memoria vía `useState` — nunca en localStorage/sessionStorage
 * (AGENTS.md, threat model FEAT-001a). Sincroniza la sesión con `client.js`
 * (que la usa para el header `Authorization` de cada request) y registra el
 * handler que limpia la sesión cuando el backend responde 401.
 *
 * Sin librería de ruteo (decisión de PLAN, spec Block 4 de FEAT-001c,
 * reafirmada en Block 3 de FEAT-001d: proyecto chico, sobre-ingeniería para
 * tres pantallas): un segundo estado local `vista` alterna entre la vista
 * pública de alta de reservas (`ReservasPublicPage`, sin sesión), el listado
 * público con filtro y cancelación (`ReservasListado`, FEAT-001d) y el login
 * de admin, detrás de botones explícitos. `"reservas"` es la vista que se
 * muestra por defecto sin sesión. Con sesión de admin activa, se muestra
 * siempre `VehiculosAdminPage`, sin importar el valor de `vista` (evita
 * quedar "atascado" en una vista pública tras loguearse).
 */
export default function App() {
  const [session, setSession] = useState(null);
  const [vista, setVista] = useState("reservas");

  useEffect(() => {
    setAuthSession(session);
  }, [session]);

  useEffect(() => {
    setUnauthorizedHandler(() => setSession(null));
  }, []);

  if (session) {
    return (
      <SessionContext.Provider value={{ session, setSession }}>
        <VehiculosAdminPage />
      </SessionContext.Provider>
    );
  }

  if (vista === "login") {
    return (
      <SessionContext.Provider value={{ session, setSession }}>
        <div>
          <nav>
            <button type="button" onClick={() => setVista("reservas")}>
              Volver a reservas
            </button>
          </nav>
          <LoginAdmin />
        </div>
      </SessionContext.Provider>
    );
  }

  return (
    <SessionContext.Provider value={{ session, setSession }}>
      <div>
        <nav>
          <button type="button" onClick={() => setVista("reservas")}>
            Reservar vehículo
          </button>
          <button type="button" onClick={() => setVista("listado")}>
            Ver reservas
          </button>
          <button type="button" onClick={() => setVista("login")}>
            Acceso administrador
          </button>
        </nav>
        {vista === "listado" ? <ReservasListado /> : <ReservasPublicPage />}
      </div>
    </SessionContext.Provider>
  );
}
