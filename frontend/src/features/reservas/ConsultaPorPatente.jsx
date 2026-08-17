import { useState } from "react";
import { consultarReservasActivasPorVehiculo } from "./reservasApi";

const MENSAJES_ERROR = {
  404: "No se encontró ningún vehículo con esa patente.",
  422: "La patente ingresada no tiene un formato válido.",
  429: "Demasiadas solicitudes. Esperá unos minutos e intentá de nuevo.",
};

/**
 * El `404` de este diccionario es propio de este contexto ("no existe ese
 * vehículo") y distinto del `404` de `ReservasListado.jsx` ("la reserva ya
 * no existe") — por eso no se comparte el diccionario entre ambos
 * componentes, aunque el patrón `mensajeDeError` sea el mismo.
 */
function mensajeDeError(error) {
  return (
    MENSAJES_ERROR[error.status] ||
    (typeof error.detail === "string" ? error.detail : null) ||
    error.message ||
    "Ocurrió un error inesperado."
  );
}

function formatFecha(valorIso) {
  return new Date(valorIso).toLocaleString();
}

/**
 * Panel de búsqueda independiente de reservas activas por patente
 * (FR-01/FR-02/FR-03/FR-04, Block 3). A diferencia de `ReservasListado`, no
 * consulta al montar: la búsqueda es on-demand, disparada al enviar el
 * formulario.
 *
 * Desacoplamiento explícito (resuelve el WARN del arch-auditor de PLAN): no
 * recibe props de `ReservasListado` ni le notifica nada al encontrar
 * resultados — no refresca ni filtra el listado general, no comparte
 * estado. Es solo un panel montado arriba del listado en la misma página.
 */
export default function ConsultaPorPatente() {
  const [patente, setPatente] = useState("");
  const [reservas, setReservas] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setReservas(null);
    setLoading(true);
    try {
      const data = await consultarReservasActivasPorVehiculo(patente.trim());
      setReservas(data);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} aria-label="Buscar reservas">
        <label htmlFor="patente-busqueda">Patente</label>
        <input
          id="patente-busqueda"
          name="patente"
          required
          value={patente}
          onChange={(event) => setPatente(event.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Buscando..." : "Buscar"}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}
      {reservas !== null && reservas.length === 0 && (
        <p role="status">Este vehículo no tiene reservas activas.</p>
      )}

      {reservas !== null && reservas.length > 0 && (
        <ul>
          {reservas.map((reserva) => (
            <li key={reserva.id}>
              {reserva.nombre_empleado} — {formatFecha(reserva.fecha_inicio)}–{formatFecha(reserva.fecha_fin)} —{" "}
              {reserva.destino}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
