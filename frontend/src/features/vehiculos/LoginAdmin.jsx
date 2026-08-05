import { useState } from "react";
import { useSession } from "../../context/SessionContext";
import { listarVehiculos } from "./vehiculosApi";

const MENSAJES_ERROR = {
  401: "Usuario o contraseña incorrectos.",
  429: "Demasiados intentos fallidos. Intente nuevamente en unos minutos.",
};

function mensajeDeError(error) {
  return MENSAJES_ERROR[error.status] || error.detail || "No se pudo iniciar sesión. Intente nuevamente.";
}

/**
 * Formulario de login del admin. El backend no expone un endpoint de login
 * dedicado (HTTP Basic se valida por request) — para confirmar las
 * credenciales antes de poblar la sesión, se usa `GET /vehiculos` como
 * "probe": si responde 200, la sesión es válida; si responde 401, se
 * descarta sin poblar la sesión. (Asunción documentada en el reporte del
 * bloque: la spec no define un endpoint de login explícito.)
 *
 * El probe pasa las credenciales tecleadas vía la opción `auth` de axios
 * (por-request), sin escribir el estado de sesión compartido de
 * `client.js` — ese estado lo escribe únicamente `App.jsx` cuando la sesión
 * (ya confirmada) cambia. Un solo escritor evita la condición de dos
 * escritores del mismo estado mutable (hallazgo de daw-arch-auditor).
 */
export default function LoginAdmin() {
  const { setSession } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await listarVehiculos({ auth: { username, password } });
      setSession({ username, password });
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Iniciar sesión">
      <h1>Administración del pool de vehículos</h1>

      <label htmlFor="username">Usuario</label>
      <input
        id="username"
        name="username"
        autoComplete="username"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        required
      />

      <label htmlFor="password">Contraseña</label>
      <input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        required
      />

      <button type="submit" disabled={loading}>
        {loading ? "Ingresando..." : "Ingresar"}
      </button>

      {error && <p role="alert">{error}</p>}
    </form>
  );
}
