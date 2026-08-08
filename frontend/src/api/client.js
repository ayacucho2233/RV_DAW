import axios from "axios";

/**
 * Cliente HTTP centralizado (AGENTS.md: "Usar un cliente HTTP centralizado
 * para todas las llamadas a la API"). La URL base viene exclusivamente de
 * `VITE_API_URL` — nunca hardcodeada (AGENTS.md).
 *
 * La sesión del admin (`{ username, password }`) vive en memoria, en el
 * estado de React de `App.jsx` (contexto `SessionContext`). Este módulo NO
 * la persiste: `setAuthSession` solo la guarda en una variable de módulo en
 * memoria, sincronizada por `App.jsx` cada vez que la sesión cambia — nunca
 * en `localStorage`/`sessionStorage` (prohibición explícita de AGENTS.md y
 * del threat model de FEAT-001a).
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

let sesionActual = null;
let manejadorNoAutorizado = null;

/** Llamado por `App.jsx` cada vez que la sesión (en memoria) cambia. */
export function setAuthSession(session) {
  sesionActual = session;
}

/** Llamado por `App.jsx` para registrar qué hacer ante un 401 (limpiar sesión y volver a LoginAdmin). */
export function setUnauthorizedHandler(handler) {
  manejadorNoAutorizado = handler;
}

apiClient.interceptors.request.use((config) => {
  if (sesionActual) {
    const token =
      typeof btoa === "function"
        ? btoa(`${sesionActual.username}:${sesionActual.password}`)
        : Buffer.from(`${sesionActual.username}:${sesionActual.password}`).toString("base64");
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Basic ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sesionActual = null;
      if (manejadorNoAutorizado) {
        manejadorNoAutorizado();
      }
    }
    return Promise.reject(error);
  },
);

export default apiClient;
