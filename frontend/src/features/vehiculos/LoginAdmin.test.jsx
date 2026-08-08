import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionContext } from "../../context/SessionContext";
import LoginAdmin from "./LoginAdmin";
import { listarVehiculos } from "./vehiculosApi";

// LoginAdmin no tiene un endpoint /login dedicado (el backend valida
// credenciales por request, vía HTTP Basic). Para verificar las credenciales
// antes de poblar la sesión, usamos GET /vehiculos como "probe" — ver
// assumption documentada en el reporte del bloque. El probe pasa las
// credenciales tecleadas vía la opción `auth` de axios (per-request), sin
// tocar el estado compartido de `client.js` — solo `App.jsx` escribe la
// sesión compartida (hallazgo de daw-arch-auditor: doble escritor).
vi.mock("./vehiculosApi", () => ({
  listarVehiculos: vi.fn(),
}));

function renderConSesion(setSession = vi.fn()) {
  render(
    <SessionContext.Provider value={{ session: null, setSession }}>
      <LoginAdmin />
    </SessionContext.Provider>,
  );
  return { setSession };
}

describe("LoginAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("envía las credenciales y puebla la sesión cuando son válidas", async () => {
    listarVehiculos.mockResolvedValueOnce([]);
    const { setSession } = renderConSesion();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/usuario/i), "admin");
    await user.type(screen.getByLabelText(/contraseña/i), "secreto123");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    await waitFor(() => {
      expect(setSession).toHaveBeenCalledWith({ username: "admin", password: "secreto123" });
    });
  });

  it("usa las credenciales ingresadas en el probe, sin depender del estado compartido del cliente", async () => {
    listarVehiculos.mockResolvedValueOnce([]);
    renderConSesion();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/usuario/i), "admin");
    await user.type(screen.getByLabelText(/contraseña/i), "secreto123");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    await waitFor(() => {
      expect(listarVehiculos).toHaveBeenCalledWith({
        auth: { username: "admin", password: "secreto123" },
      });
    });
  });

  it("en 401 muestra el error y no puebla la sesión", async () => {
    const error = new Error("Credenciales inválidas");
    error.status = 401;
    error.detail = "Credenciales inválidas";
    listarVehiculos.mockRejectedValueOnce(error);
    const { setSession } = renderConSesion();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/usuario/i), "admin");
    await user.type(screen.getByLabelText(/contraseña/i), "incorrecta");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/usuario o contraseña/i);
    expect(setSession).not.toHaveBeenCalled();
  });
});
