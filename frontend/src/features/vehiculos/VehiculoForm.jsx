import { useState } from "react";
import { crearVehiculo, modificarVehiculo } from "./vehiculosApi";

const TIPOS_PERMITIDOS = [
  { value: "auto", label: "Auto" },
  { value: "camioneta", label: "Camioneta" },
];

const MENSAJES_ERROR = {
  400: "El tipo de vehículo no es válido.",
  401: "La sesión expiró. Volvé a iniciar sesión.",
  404: "El vehículo no existe o ya fue eliminado.",
  409: "Ya existe un vehículo con esa patente.",
  429: "Demasiados intentos. Esperá unos minutos e intentá de nuevo.",
};

function mensajeDeError(error) {
  return MENSAJES_ERROR[error.status] || error.detail || "Ocurrió un error inesperado.";
}

/**
 * Alta/edición de un vehículo (FR-01/FR-02). Validaciones de cliente
 * (patente requerida, tipo restringido a los 2 valores vía <select>) no
 * reemplazan la validación del backend, que revalida todo (AGENTS.md).
 */
export default function VehiculoForm({ vehiculo, onSuccess, onCancel }) {
  const esEdicion = Boolean(vehiculo);
  const [patente, setPatente] = useState(vehiculo?.patente ?? "");
  const [tipo, setTipo] = useState(vehiculo?.tipo ?? TIPOS_PERMITIDOS[0].value);
  const [patenteError, setPatenteError] = useState(null);
  const [error, setError] = useState(null);
  const [exito, setExito] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setExito(null);

    const patenteLimpia = patente.trim();
    if (!patenteLimpia) {
      setPatenteError("La patente es obligatoria.");
      return;
    }
    setPatenteError(null);

    setLoading(true);
    try {
      const payload = { patente: patenteLimpia, tipo };
      const resultado = esEdicion
        ? await modificarVehiculo(vehiculo.id, payload)
        : await crearVehiculo(payload);
      // El mensaje de éxito se muestra ANTES de notificar al padre: el
      // padre (VehiculosAdminPage) actualiza su lista con `onSuccess` pero
      // ya no cierra el form automáticamente — el admin lo cierra con
      // "Cancelar" una vez que vio la confirmación (evita que el mensaje
      // desaparezca por un desmontaje inmediato).
      setExito(esEdicion ? "Vehículo actualizado con éxito." : "Vehículo creado con éxito.");
      onSuccess?.(resultado);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label={esEdicion ? "Editar vehículo" : "Agregar vehículo"}>
      <label htmlFor="patente">Patente</label>
      <input
        id="patente"
        name="patente"
        value={patente}
        onChange={(event) => setPatente(event.target.value)}
      />
      {patenteError && <p role="alert">{patenteError}</p>}

      <label htmlFor="tipo">Tipo</label>
      <select id="tipo" name="tipo" value={tipo} onChange={(event) => setTipo(event.target.value)}>
        {TIPOS_PERMITIDOS.map((opcion) => (
          <option key={opcion.value} value={opcion.value}>
            {opcion.label}
          </option>
        ))}
      </select>

      <button type="submit" disabled={loading}>
        {loading ? "Guardando..." : "Guardar"}
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} disabled={loading}>
          Cancelar
        </button>
      )}

      {error && <p role="alert">{error}</p>}
      {exito && <p role="status">{exito}</p>}
    </form>
  );
}
