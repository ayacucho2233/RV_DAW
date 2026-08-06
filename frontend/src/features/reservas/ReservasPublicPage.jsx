import { useCallback, useEffect, useState } from "react";
import { listarVehiculosPool, consultarDisponibilidad } from "./reservasApi";
import ReservaForm from "./ReservaForm";

const MENSAJES_ERROR = {
  422: "El rango de fechas ingresado no es válido.",
  429: "Demasiadas consultas. Esperá unos minutos e intentá de nuevo.",
};

function mensajeDeError(error) {
  return (
    MENSAJES_ERROR[error.status] ||
    (typeof error.detail === "string" ? error.detail : null) ||
    error.message ||
    "Ocurrió un error inesperado."
  );
}

/**
 * Convierte el valor de un `<input type="datetime-local">` a un string ISO
 * 8601 con zona horaria — mismo criterio que `ReservaForm.jsx`.
 */
function aIsoConTimezone(valorDatetimeLocal) {
  return new Date(valorDatetimeLocal).toISOString();
}

/**
 * Vista pública sin autenticación: lista el pool de vehículos (FR-01), deja
 * elegir un vehículo + rango de fechas para consultar disponibilidad
 * (FR-04) antes de abrir `ReservaForm` con ese vehículo/rango precargado —
 * mejora de UX no exigida por AC, pero consistente con NFR-01 (completar
 * una reserva en menos de 1 minuto): evita reservar sobre un vehículo que
 * ya se sabe no disponible.
 */
export default function ReservasPublicPage() {
  const [vehiculos, setVehiculos] = useState([]);
  const [loadingVehiculos, setLoadingVehiculos] = useState(false);
  const [vehiculosError, setVehiculosError] = useState(null);

  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [disponibilidad, setDisponibilidad] = useState(null);
  const [loadingDisponibilidad, setLoadingDisponibilidad] = useState(false);
  const [dispError, setDispError] = useState(null);

  const [vehiculoElegido, setVehiculoElegido] = useState(null);
  const [reservaExito, setReservaExito] = useState(null);

  const cargarVehiculos = useCallback(async () => {
    setLoadingVehiculos(true);
    setVehiculosError(null);
    try {
      const data = await listarVehiculosPool();
      setVehiculos(data);
    } catch (error) {
      setVehiculosError(mensajeDeError(error));
    } finally {
      setLoadingVehiculos(false);
    }
  }, []);

  useEffect(() => {
    cargarVehiculos();
  }, [cargarVehiculos]);

  async function handleConsultarDisponibilidad(event) {
    event.preventDefault();
    setDispError(null);
    setDisponibilidad(null);
    setVehiculoElegido(null);
    setLoadingDisponibilidad(true);
    try {
      const data = await consultarDisponibilidad(aIsoConTimezone(desde), aIsoConTimezone(hasta));
      setDisponibilidad(data);
    } catch (error) {
      setDispError(mensajeDeError(error));
    } finally {
      setLoadingDisponibilidad(false);
    }
  }

  function handleElegirVehiculo(item) {
    setReservaExito(null);
    setVehiculoElegido(item);
  }

  function handleReservaExitosa() {
    setReservaExito("Reserva confirmada con éxito.");
    setVehiculoElegido(null);
  }

  function handleCancelarReserva() {
    setVehiculoElegido(null);
  }

  return (
    <div>
      <h1>Reservar un vehículo</h1>

      <section aria-label="Vehículos del pool">
        <h2>Vehículos del pool</h2>
        {loadingVehiculos && <p>Cargando vehículos...</p>}
        {vehiculosError && <p role="alert">{vehiculosError}</p>}
        <ul>
          {vehiculos.map((vehiculo, indice) => (
            <li key={`${vehiculo.patente}-${indice}`}>
              {vehiculo.patente} — {vehiculo.tipo}
            </li>
          ))}
        </ul>
      </section>

      <form onSubmit={handleConsultarDisponibilidad} aria-label="Consultar disponibilidad">
        <label htmlFor="desde">Desde</label>
        <input
          id="desde"
          name="desde"
          type="datetime-local"
          value={desde}
          onChange={(event) => setDesde(event.target.value)}
          required
        />

        <label htmlFor="hasta">Hasta</label>
        <input
          id="hasta"
          name="hasta"
          type="datetime-local"
          value={hasta}
          onChange={(event) => setHasta(event.target.value)}
          required
        />

        <button type="submit" disabled={loadingDisponibilidad}>
          {loadingDisponibilidad ? "Consultando..." : "Consultar disponibilidad"}
        </button>
      </form>

      {dispError && <p role="alert">{dispError}</p>}

      {disponibilidad && (
        <ul>
          {disponibilidad.map((item) => (
            <li key={item.vehiculo_id}>
              <span>
                {item.patente} — {item.tipo} — {item.disponible ? "Disponible" : "No disponible"}
              </span>
              {item.disponible && (
                <button type="button" onClick={() => handleElegirVehiculo(item)}>
                  Reservar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {reservaExito && <p role="status">{reservaExito}</p>}

      {vehiculoElegido && (
        <ReservaForm
          vehiculos={disponibilidad.filter((item) => item.disponible)}
          vehiculoInicialId={vehiculoElegido.vehiculo_id}
          fechaInicioInicial={desde}
          fechaFinInicial={hasta}
          onSuccess={handleReservaExitosa}
          onCancel={handleCancelarReserva}
        />
      )}
    </div>
  );
}
