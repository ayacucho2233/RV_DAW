import { useEffect, useState } from "react";
import { SessionContext } from "./context/SessionContext";
import { setAuthSession, setUnauthorizedHandler } from "./api/client";
import { caducarReservasVencidas } from "./features/reservas/reservasApi";
import LoginAdmin from "./features/vehiculos/LoginAdmin";
import VehiculosAdminPage from "./features/vehiculos/VehiculosAdminPage";
import ReservasPublicPage from "./features/reservas/ReservasPublicPage";
import ReservasListado from "./features/reservas/ReservasListado";
import MenuPrincipal from "./features/menu/MenuPrincipal";
import { IconArrowLeft, IconLogout } from "./components/icons";

/**
 * Raíz de la app. Mantiene la sesión del admin (`{ username, password } |
 * null`) en memoria vía `useState` — nunca en localStorage/sessionStorage
 * (AGENTS.md, threat model FEAT-001a). Sincroniza la sesión con `client.js`
 * (que la usa para el header `Authorization` de cada request) y registra el
 * handler que limpia la sesión cuando el backend responde 401.
 *
 * Sin librería de ruteo (decisión de PLAN, spec Block 4 de FEAT-001c,
 * reafirmada en Block 3 de FEAT-001d y en spec FEAT-002 Block 3: proyecto
 * chico, sobre-ingeniería para cuatro pantallas): un segundo estado local
 * `vista` alterna entre 4 valores — `"menu"` (nuevo estado inicial, punto de
 * entrada de FEAT-002), `"consultar"` (alta/disponibilidad de reservas,
 * `ReservasPublicPage`), `"gestionar"` (listado/filtro/cancelación,
 * `ReservasListado`) y `"admin"` (login, `LoginAdmin`), detrás de botones
 * explícitos del menú principal (`MenuPrincipal`) o del header de navegación
 * (`<header className="app-header">`, botón "Volver al menú").
 *
 * El guard de sesión (`if (session) return <VehiculosAdminPage />`) sigue
 * teniendo prioridad absoluta sobre `vista` — decisión de PLAN confirmada con
 * el usuario (spec FEAT-002, Summary): con sesión de admin activa, la app
 * SIEMPRE muestra el panel admin, sin importar `vista`. No es un bug: un
 * admin logueado NUNCA ve `ReservasPublicPage`/`ReservasListado`
 * directamente; para navegar ahí primero tiene que cerrar sesión. Por eso,
 * dentro de esa rama, "Volver al menú" también cierra la sesión (es la única
 * forma de que el botón tenga efecto visible dado que el guard tiene
 * prioridad), mientras que "Cerrar sesión" cierra la sesión pero permanece
 * en la rama Administrador (vuelve a mostrar el login) — ambos botones son
 * independientes (AC-06) con destinos distintos, sin reabrir el guard.
 */
export default function App() {
  const [session, setSession] = useState(null);
  const [vista, setVista] = useState("menu");

  useEffect(() => {
    // FEAT-005 (Block 4): dispara el sweep de reservas vencidas una sola vez
    // al entrar al programa desde el explorador (decisión de PLAN). Fire-
    // and-forget: no bloquea el render de MenuPrincipal.
    //
    // Excepción explícita a "Nunca captura silenciosa" de AGENTS.md: es una
    // llamada de mantenimiento en background, sin ninguna acción de usuario
    // a la que traducir un mensaje visible de error, y un fallo acá no
    // degrada la app (una reserva que no caducó todavía lo hace en el
    // próximo mount). Se loguea a console.error para no perder la señal por
    // completo.
    caducarReservasVencidas().catch((error) => {
      console.error("No se pudo caducar las reservas vencidas al montar la app.", error);
    });
  }, []);

  useEffect(() => {
    setAuthSession(session);
  }, [session]);

  useEffect(() => {
    setUnauthorizedHandler(() => setSession(null));
  }, []);

  if (session) {
    return (
      <SessionContext.Provider value={{ session, setSession }}>
        <header className="app-header">
          <button type="button" onClick={() => setSession(null)}>
            <IconLogout aria-hidden="true" /> Cerrar sesión
          </button>
          <button
            type="button"
            onClick={() => {
              setSession(null);
              setVista("menu");
            }}
          >
            <IconArrowLeft aria-hidden="true" /> Volver al menú
          </button>
        </header>
        <VehiculosAdminPage />
      </SessionContext.Provider>
    );
  }

  if (vista === "menu") {
    return <MenuPrincipal onSelect={setVista} />;
  }

  return (
    <SessionContext.Provider value={{ session, setSession }}>
      <header className="app-header">
        <button type="button" onClick={() => setVista("menu")}>
          <IconArrowLeft aria-hidden="true" /> Volver al menú
        </button>
      </header>
      {vista === "consultar" && <ReservasPublicPage />}
      {vista === "gestionar" && <ReservasListado />}
      {vista === "admin" && <LoginAdmin />}
    </SessionContext.Provider>
  );
}
