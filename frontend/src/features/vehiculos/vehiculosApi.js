import apiClient from "../../api/client";

/**
 * Capa de acceso a los 6 endpoints de `/vehiculos` (contrato definido en
 * Block 3 de la spec). Nunca falla en silencio: siempre propaga un `Error`
 * tipado con `.status` (código HTTP del backend) y `.detail` (el `detail`
 * del body de error de FastAPI), para que los componentes lo traduzcan a un
 * mensaje visible según el código (AGENTS.md: "Tipear errores; nunca captura
 * silenciosa").
 */
function propagarError(error) {
  if (error.response) {
    const err = new Error(error.response.data?.detail || "Ocurrió un error inesperado.");
    err.status = error.response.status;
    err.detail = error.response.data?.detail;
    throw err;
  }
  const err = new Error("No se pudo conectar con el servidor.");
  err.status = null;
  err.detail = null;
  throw err;
}

/**
 * `config` (opcional) se reenvía tal cual a axios. Lo usa `LoginAdmin.jsx`
 * para pasar `{ auth: { username, password } }` por-request al validar
 * credenciales nuevas, sin depender del estado de sesión compartido de
 * `client.js` (que solo `App.jsx` escribe).
 */
export async function listarVehiculos(config) {
  try {
    const { data } = await apiClient.get("/vehiculos", config);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

export async function crearVehiculo(payload) {
  try {
    const { data } = await apiClient.post("/vehiculos", payload);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

export async function modificarVehiculo(id, payload) {
  try {
    const { data } = await apiClient.put(`/vehiculos/${id}`, payload);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

export async function bajaTemporal(id) {
  try {
    const { data } = await apiClient.patch(`/vehiculos/${id}/baja-temporal`);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

export async function bajaDefinitiva(id) {
  try {
    const { data } = await apiClient.patch(`/vehiculos/${id}/baja-definitiva`);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}

export async function reactivarVehiculo(id) {
  try {
    const { data } = await apiClient.patch(`/vehiculos/${id}/reactivar`);
    return data;
  } catch (error) {
    return propagarError(error);
  }
}
