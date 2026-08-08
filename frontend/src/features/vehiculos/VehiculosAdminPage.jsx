import { useCallback, useEffect, useState } from "react";
import { useSession } from "../../context/SessionContext";
import {
  listarVehiculos,
  bajaTemporal,
  bajaDefinitiva,
  reactivarVehiculo,
} from "./vehiculosApi";
import VehiculoForm from "./VehiculoForm";

const MENSAJES_ERROR = {
  400: "Los datos ingresados no son válidos.",
  401: "La sesión expiró. Volvé a iniciar sesión.",
  404: "El vehículo no existe o ya fue eliminado.",
  429: "Demasiados intentos. Esperá unos minutos e intentá de nuevo.",
};

function mensajeDeError(error) {
  return MENSAJES_ERROR[error.status] || error.detail || error.message || "Ocurrió un error inesperado.";
}

const ACCIONES = {
  "baja-temporal": { etiqueta: "Baja temporal", fn: bajaTemporal, estadosPermitidos: ["activo"] },
  "baja-definitiva": {
    etiqueta: "Baja definitiva",
    fn: bajaDefinitiva,
    estadosPermitidos: ["activo", "baja_temporal"],
  },
  reactivar: { etiqueta: "Reactivar", fn: reactivarVehiculo, estadosPermitidos: ["baja_temporal"] },
};

/**
 * Clave única de una acción en curso: una por combinación vehículo+tipo, no
 * una sola global — evita que dos acciones simultáneas sobre vehículos
 * distintos se pisen entre sí (hallazgo de daw-arch-auditor).
 */
function claveAccion(id, tipo) {
  return `${id}:${tipo}`;
}

/**
 * Lista de vehículos del pool + acciones de administración (baja temporal,
 * baja definitiva, reactivar) y alta/edición vía `VehiculoForm`. Todas las
 * acciones async muestran loading/éxito/error explícitos — nunca fallan en
 * silencio ni bloquean la UI completa (AGENTS.md).
 */
export default function VehiculosAdminPage() {
  const { setSession } = useSession();
  const [vehiculos, setVehiculos] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const [listError, setListError] = useState(null);
  const [accionesEnCurso, setAccionesEnCurso] = useState(() => new Set());
  const [accionError, setAccionError] = useState(null);
  const [accionExito, setAccionExito] = useState(null);
  const [formAbierto, setFormAbierto] = useState(false);
  const [vehiculoEditando, setVehiculoEditando] = useState(null);

  const cargarVehiculos = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const data = await listarVehiculos();
      setVehiculos(data);
    } catch (error) {
      if (error.status === 401) {
        setSession(null);
        return;
      }
      setListError(mensajeDeError(error));
    } finally {
      setLoadingList(false);
    }
  }, [setSession]);

  useEffect(() => {
    cargarVehiculos();
  }, [cargarVehiculos]);

  async function ejecutarAccion(id, tipo) {
    const clave = claveAccion(id, tipo);
    setAccionesEnCurso((previas) => {
      const siguientes = new Set(previas);
      siguientes.add(clave);
      return siguientes;
    });
    setAccionError(null);
    setAccionExito(null);
    try {
      const actualizado = await ACCIONES[tipo].fn(id);
      setVehiculos((previos) => previos.map((v) => (v.id === id ? actualizado : v)));
      setAccionExito(`${ACCIONES[tipo].etiqueta} realizada con éxito.`);
    } catch (error) {
      if (error.status === 401) {
        setSession(null);
        return;
      }
      setAccionError(mensajeDeError(error));
    } finally {
      setAccionesEnCurso((previas) => {
        const siguientes = new Set(previas);
        siguientes.delete(clave);
        return siguientes;
      });
    }
  }

  function estaEnCurso(id, tipo) {
    return accionesEnCurso.has(claveAccion(id, tipo));
  }

  function handleNuevo() {
    setVehiculoEditando(null);
    setFormAbierto(true);
  }

  function handleEditar(vehiculo) {
    setVehiculoEditando(vehiculo);
    setFormAbierto(true);
  }

  function handleGuardado(vehiculo) {
    // No cierra el form automáticamente: `VehiculoForm` ya muestra su propio
    // mensaje de éxito y el admin lo cierra manualmente con "Cancelar" — si
    // lo cerráramos acá, el mensaje de confirmación nunca llegaría a verse
    // (hallazgo de daw-module-verifier/daw-arch-auditor).
    setVehiculos((previos) => {
      const yaExiste = previos.some((v) => v.id === vehiculo.id);
      return yaExiste
        ? previos.map((v) => (v.id === vehiculo.id ? vehiculo : v))
        : [...previos, vehiculo];
    });
  }

  function handleCerrarForm() {
    setFormAbierto(false);
    setVehiculoEditando(null);
  }

  return (
    <div>
      <h1>Pool de vehículos</h1>
      <button type="button" onClick={handleNuevo}>
        Agregar vehículo
      </button>

      {formAbierto && (
        <VehiculoForm vehiculo={vehiculoEditando} onSuccess={handleGuardado} onCancel={handleCerrarForm} />
      )}

      {loadingList && <p>Cargando vehículos...</p>}
      {listError && <p role="alert">{listError}</p>}
      {accionError && <p role="alert">{accionError}</p>}
      {accionExito && <p role="status">{accionExito}</p>}

      <ul>
        {vehiculos.map((vehiculo) => (
          <li key={vehiculo.id}>
            <span>
              {vehiculo.patente} — {vehiculo.tipo} — {vehiculo.estado}
            </span>
            <button type="button" onClick={() => handleEditar(vehiculo)}>
              Editar
            </button>
            {Object.entries(ACCIONES).map(([tipo, { etiqueta, estadosPermitidos }]) =>
              estadosPermitidos.includes(vehiculo.estado) ? (
                <button
                  key={tipo}
                  type="button"
                  disabled={estaEnCurso(vehiculo.id, tipo)}
                  onClick={() => ejecutarAccion(vehiculo.id, tipo)}
                >
                  {estaEnCurso(vehiculo.id, tipo) ? "Procesando..." : etiqueta}
                </button>
              ) : null,
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
