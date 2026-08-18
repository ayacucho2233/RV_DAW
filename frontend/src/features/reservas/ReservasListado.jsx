import { useCallback, useEffect, useState } from "react";
import { listarReservas, cancelarReserva } from "./reservasApi";
import ConsultaPorPatente from "./ConsultaPorPatente";

const MENSAJES_ERROR = {
  403: "El legajo indicado no coincide con el de la reserva.",
  404: "La reserva ya no existe.",
  409: "La reserva ya se encuentra cancelada.",
  422: "El legajo es obligatorio.",
  429: "Demasiadas solicitudes. Esperá unos minutos e intentá de nuevo.",
};

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
 * Listado público de reservas (FR-01/FR-02), con filtro opcional por
 * período y cancelación de reservas propias (FR-03/AC-06). También aloja,
 * por encima del listado, el panel independiente `<ConsultaPorPatente />`
 * (FR-04, Block 3), desacoplado de este estado. Al montar pide
 * `GET /reservas` sin filtro (`periodo` inicial `""` → `undefined`); el
 * `<select>` de período dispara una nueva consulta al cambiar.
 *
 * La cancelación usa un `<form>` inline por fila con un `<input>`
 * controlado para `legajo` — nunca `window.prompt`/`window.confirm`
 * (hallazgo del arch-auditor en PLAN, spec Block 3: el resto del frontend
 * usa exclusivamente inputs controlados, y los diálogos nativos no son
 * testeables con la config actual de Vitest/Testing Library). Solo un
 * formulario de cancelación puede estar abierto a la vez.
 */
export default function ReservasListado() {
  const [reservas, setReservas] = useState([]);
  const [periodo, setPeriodo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [filaAbiertaId, setFilaAbiertaId] = useState(null);
  const [legajoInput, setLegajoInput] = useState("");
  const [cancelando, setCancelando] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [mensajeCancelacion, setMensajeCancelacion] = useState(null);

  const cargarReservas = useCallback(async (periodoActual) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listarReservas(periodoActual || undefined);
      setReservas(data);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarReservas(periodo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo]);

  function abrirCancelacion(reservaId) {
    setFilaAbiertaId(reservaId);
    setLegajoInput("");
    setValidationError(null);
    setMensajeCancelacion(null);
  }

  async function handleCancelarSubmit(event, reserva) {
    event.preventDefault();
    setValidationError(null);

    const legajoLimpio = legajoInput.trim();
    if (!legajoLimpio) {
      setValidationError("El legajo es obligatorio.");
      return;
    }

    setCancelando(true);
    try {
      await cancelarReserva(reserva.id, legajoLimpio);
      setMensajeCancelacion({ reservaId: reserva.id, tipo: "exito", texto: "Reserva cancelada con éxito." });
      setFilaAbiertaId(null);
      await cargarReservas(periodo);
    } catch (err) {
      setMensajeCancelacion({ reservaId: reserva.id, tipo: "error", texto: mensajeDeError(err) });
    } finally {
      setCancelando(false);
    }
  }

  return (
    <div>
      <ConsultaPorPatente />

      <h1>Reservas</h1>

      <label htmlFor="periodo">Período</label>
      <select id="periodo" name="periodo" value={periodo} onChange={(event) => setPeriodo(event.target.value)}>
        <option value="">Todas</option>
        <option value="futuras">Futuras</option>
        <option value="en_curso">En curso</option>
        <option value="pasadas">Pasadas</option>
      </select>

      {loading && <p>Cargando reservas...</p>}
      {error && <p role="alert">{error}</p>}
      {mensajeCancelacion?.tipo === "exito" && <p role="status">{mensajeCancelacion.texto}</p>}

      <ul>
        {reservas.map((reserva) => (
          <li key={reserva.id}>
            <span>
              {reserva.patente} — {reserva.tipo} — {reserva.nombre_empleado} — {formatFecha(reserva.fecha_inicio)}
              –{formatFecha(reserva.fecha_fin)} — {reserva.destino} — estado: {reserva.estado}
            </span>

            {reserva.estado === "activa" &&
              (filaAbiertaId === reserva.id ? (
                <form onSubmit={(event) => handleCancelarSubmit(event, reserva)} aria-label="Cancelar reserva">
                  <label htmlFor={`legajo-${reserva.id}`}>Legajo</label>
                  <input
                    id={`legajo-${reserva.id}`}
                    name="legajo"
                    value={legajoInput}
                    onChange={(event) => setLegajoInput(event.target.value)}
                  />
                  <button type="submit" disabled={cancelando}>
                    {cancelando ? "Cancelando..." : "Confirmar cancelación"}
                  </button>
                  <button type="button" onClick={() => setFilaAbiertaId(null)} disabled={cancelando}>
                    Volver
                  </button>
                  {validationError && <p role="alert">{validationError}</p>}
                </form>
              ) : (
                <button type="button" onClick={() => abrirCancelacion(reserva.id)}>
                  Cancelar
                </button>
              ))}

            {mensajeCancelacion?.reservaId === reserva.id && mensajeCancelacion.tipo === "error" && (
              <p role="alert">{mensajeCancelacion.texto}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
