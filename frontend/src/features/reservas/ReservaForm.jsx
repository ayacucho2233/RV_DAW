import { useState } from "react";
import { crearReserva } from "./reservasApi";

const MENSAJES_ERROR = {
  404: "El vehículo elegido ya no existe. Volvé a consultar disponibilidad.",
  422: "Revisá los datos: todos los campos son obligatorios y la fecha de fin debe ser posterior a la de inicio.",
  429: "Demasiadas solicitudes. Esperá unos minutos e intentá de nuevo.",
};

/**
 * Traduce el error del backend a un mensaje legible. El 409 tiene DOS
 * causas distintas (vehículo no activo / solapamiento de reservas, ver
 * `backend/app/features/reservas/exceptions.py`) — se distingue por el
 * `detail` que ya envía el backend, en vez de usar un mensaje genérico de
 * "conflicto" (mandato explícito del spec, Block 4).
 */
function mensajeDeError(error) {
  if (error.status === 409) {
    if (typeof error.detail === "string" && error.detail.toLowerCase().includes("no está disponible")) {
      return "El vehículo no está disponible para reservas (fue dado de baja).";
    }
    return "Ya existe una reserva activa que se superpone con ese período para este vehículo.";
  }
  return (
    MENSAJES_ERROR[error.status] ||
    (typeof error.detail === "string" ? error.detail : null) ||
    "Ocurrió un error inesperado."
  );
}

/**
 * Convierte el valor de un `<input type="datetime-local">` (hora local del
 * navegador, sin zona horaria) a un string ISO 8601 CON zona horaria
 * (`toISOString()` siempre produce UTC con sufijo `Z`) — el backend exige
 * timezone-aware obligatorio (TM-C-03, ver `schemas.py` de Block 2).
 */
function aIsoConTimezone(valorDatetimeLocal) {
  return new Date(valorDatetimeLocal).toISOString();
}

/**
 * Formulario de alta de una reserva (FR-02). Validación de cliente (campos
 * requeridos + `fecha_fin > fecha_inicio`) no reemplaza la validación del
 * backend, que revalida todo igual (AGENTS.md, AC-03/AC-04).
 *
 * `vehiculos`: lista de `{ vehiculo_id, patente, tipo }` ya consultada por
 * el padre (`ReservasPublicPage`, vía `GET /reservas/disponibilidad`) — el
 * select solo ofrece vehículos ya listados, nunca consulta por su cuenta.
 */
export default function ReservaForm({
  vehiculos = [],
  vehiculoInicialId,
  fechaInicioInicial,
  fechaFinInicial,
  onSuccess,
  onCancel,
}) {
  const [nombreEmpleado, setNombreEmpleado] = useState("");
  const [legajo, setLegajo] = useState("");
  const [licencia, setLicencia] = useState("");
  const [vehiculoId, setVehiculoId] = useState(
    vehiculoInicialId != null ? String(vehiculoInicialId) : String(vehiculos[0]?.vehiculo_id ?? ""),
  );
  const [fechaInicio, setFechaInicio] = useState(fechaInicioInicial ?? "");
  const [fechaFin, setFechaFin] = useState(fechaFinInicial ?? "");
  const [destino, setDestino] = useState("");
  const [validationError, setValidationError] = useState(null);
  const [error, setError] = useState(null);
  const [exito, setExito] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setValidationError(null);
    setError(null);
    setExito(null);

    if (
      !nombreEmpleado.trim() ||
      !legajo.trim() ||
      !licencia.trim() ||
      !vehiculoId ||
      !fechaInicio ||
      !fechaFin ||
      !destino.trim()
    ) {
      setValidationError("Todos los campos son obligatorios.");
      return;
    }

    const inicio = new Date(fechaInicio);
    const fin = new Date(fechaFin);
    if (fin <= inicio) {
      setValidationError("La fecha de fin debe ser posterior a la fecha de inicio.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        nombre_empleado: nombreEmpleado.trim(),
        legajo: legajo.trim(),
        licencia: licencia.trim(),
        vehiculo_id: Number(vehiculoId),
        fecha_inicio: aIsoConTimezone(fechaInicio),
        fecha_fin: aIsoConTimezone(fechaFin),
        destino: destino.trim(),
      };
      const resultado = await crearReserva(payload);
      setExito("Reserva confirmada con éxito.");
      onSuccess?.(resultado);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Reservar vehículo">
      <label htmlFor="nombre_empleado">Nombre del empleado</label>
      <input
        id="nombre_empleado"
        name="nombre_empleado"
        value={nombreEmpleado}
        onChange={(event) => setNombreEmpleado(event.target.value)}
      />

      <label htmlFor="legajo">Legajo</label>
      <input id="legajo" name="legajo" value={legajo} onChange={(event) => setLegajo(event.target.value)} />

      <label htmlFor="licencia">Licencia de conducir</label>
      <input
        id="licencia"
        name="licencia"
        value={licencia}
        onChange={(event) => setLicencia(event.target.value)}
      />

      <label htmlFor="vehiculo_id">Vehículo</label>
      <select
        id="vehiculo_id"
        name="vehiculo_id"
        value={vehiculoId}
        onChange={(event) => setVehiculoId(event.target.value)}
      >
        {vehiculos.map((vehiculo) => (
          <option key={vehiculo.vehiculo_id} value={vehiculo.vehiculo_id}>
            {vehiculo.patente} — {vehiculo.tipo}
          </option>
        ))}
      </select>

      <label htmlFor="fecha_inicio">Fecha y hora de inicio</label>
      <input
        id="fecha_inicio"
        name="fecha_inicio"
        type="datetime-local"
        value={fechaInicio}
        onChange={(event) => setFechaInicio(event.target.value)}
      />

      <label htmlFor="fecha_fin">Fecha y hora de fin</label>
      <input
        id="fecha_fin"
        name="fecha_fin"
        type="datetime-local"
        value={fechaFin}
        onChange={(event) => setFechaFin(event.target.value)}
      />

      <label htmlFor="destino">Destino</label>
      <input id="destino" name="destino" value={destino} onChange={(event) => setDestino(event.target.value)} />

      <button type="submit" disabled={loading}>
        {loading ? "Reservando..." : "Reservar"}
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} disabled={loading}>
          Cancelar
        </button>
      )}

      {validationError && <p role="alert">{validationError}</p>}
      {error && <p role="alert">{error}</p>}
      {exito && <p role="status">{exito}</p>}
    </form>
  );
}
