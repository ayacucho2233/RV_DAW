import apiClient from "../../api/client";

/**
 * Capa de acceso a las 6 funciones públicas de `/reservas` (contrato
 * definido en Block 3 de la spec). A diferencia de `vehiculosApi.js`, NUNCA
 * pasa el header `Authorization`: estos endpoints son públicos por diseño
 * del PRD (sin autenticación de empleados), y `apiClient` (`client.js`) ya
 * no agrega ese header cuando `sesionActual` es `null` — que es el caso
 * normal para un empleado sin loguearse, y el único que este módulo usa (no
 * reenvía ningún `config` de auth por-request, a diferencia de
 * `listarVehiculos` en `vehiculosApi.js`).
 *
 * Nunca falla en silencio: siempre propaga un `Error` tipado con `.status`
 * (código HTTP del backend) y `.detail` (el `detail` del body de error de
 * FastAPI), para que los componentes lo traduzcan a un mensaje visible
 * (AGENTS.md: "Tipear errores; nunca captura silenciosa"). Mismo patrón que
 * `vehiculosApi.js`.
 */
function propagarError(error) {
  if (error.response) {
    const detalle = error.response.data?.detail;
    const mensaje = typeof detalle === "string" ? detalle : "Ocurrió un error inesperado.";
    const err = new Error(mensaje);
    err.status = error.response.status;
    err.detail = detalle;
    throw err;
  }
  const err = new Error("No se pudo conectar con el servidor.");
  err.status = null;
  err.detail = null;
  throw err;
}

/** FR-01: listado público del pool de vehículos (`patente`/`tipo`, sin `id`). */
export async function listarVehiculosPool() {
  try {
    const { data } = await apiClient.get("/reservas/vehiculos");
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

/**
 * FR-04: disponibilidad de cada vehículo del pool para el rango `[desde,
 * hasta]`. `desde`/`hasta` deben ser strings ISO 8601 con zona horaria
 * (conversión a cargo del componente que llama, igual que en
 * `ReservaForm.jsx`).
 */
export async function consultarDisponibilidad(desde, hasta) {
  try {
    const { data } = await apiClient.get("/reservas/disponibilidad", {
      params: { desde, hasta },
    });
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

/** FR-02: alta de una reserva. */
export async function crearReserva(payload) {
  try {
    const { data } = await apiClient.post("/reservas", payload);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

/**
 * FR-01/FR-02: listado público de todas las reservas, opcionalmente
 * filtrado por `periodo` (`"futuras"|"en_curso"|"pasadas"`). Solo agrega el
 * query param cuando `periodo` no es `null`/`undefined` — sin filtro, trae
 * todas (mismo criterio que documenta el spec de Block 3).
 */
export async function listarReservas(periodo) {
  try {
    const config = periodo != null ? { params: { periodo } } : undefined;
    const { data } = await apiClient.get("/reservas", config);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

/** FR-03: cancela una reserva propia validando el `legajo` de quien la creó. */
export async function cancelarReserva(id, legajo) {
  try {
    const { data } = await apiClient.patch(`/reservas/${id}/cancelar`, { legajo });
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

/** FR-01/FR-02/FR-03/FR-04: reservas activas de un vehículo dado por patente. */
export async function consultarReservasActivasPorVehiculo(patente) {
  try {
    const { data } = await apiClient.get(`/reservas/vehiculo/${patente}`);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

/**
 * FR-02: dispara el sweep masivo que transiciona a `caducada` toda reserva
 * `activa` con `fecha_fin` vencida (Block 2/3 del backend). Llamada por
 * `App.jsx` una sola vez al montar (Block 4) — ver ahí la justificación de
 * por qué el fallo de esta llamada no se propaga a la UI.
 */
export async function caducarReservasVencidas() {
  try {
    const { data } = await apiClient.post("/reservas/caducar-vencidas");
    return data;
  } catch (error) {
    return propagarError(error);
  }
}
