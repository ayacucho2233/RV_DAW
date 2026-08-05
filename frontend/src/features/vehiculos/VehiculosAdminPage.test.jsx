import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionContext } from "../../context/SessionContext";
import VehiculosAdminPage from "./VehiculosAdminPage";
import { listarVehiculos, bajaTemporal, bajaDefinitiva, reactivarVehiculo } from "./vehiculosApi";

vi.mock("./vehiculosApi", () => ({
  listarVehiculos: vi.fn(),
  bajaTemporal: vi.fn(),
  bajaDefinitiva: vi.fn(),
  reactivarVehiculo: vi.fn(),
  crearVehiculo: vi.fn(),
  modificarVehiculo: vi.fn(),
}));

const vehiculoActivo = {
  id: 1,
  patente: "AB123CD",
  tipo: "auto",
  estado: "activo",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const vehiculoEnBajaTemporal = {
  id: 2,
  patente: "XY999ZZ",
  tipo: "camioneta",
  estado: "baja_temporal",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderPage(setSession = vi.fn()) {
  render(
    <SessionContext.Provider
      value={{ session: { username: "admin", password: "x" }, setSession }}
    >
      <VehiculosAdminPage />
    </SessionContext.Provider>,
  );
}

describe("VehiculosAdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza la lista de vehículos desde GET /vehiculos", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoActivo]);
    renderPage();

    expect(await screen.findByText(/AB123CD/)).toBeInTheDocument();
  });

  it("dispara la baja temporal, muestra loading y luego actualiza el estado", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoActivo]);
    let resolverBaja;
    bajaTemporal.mockReturnValueOnce(
      new Promise((resolve) => {
        resolverBaja = resolve;
      }),
    );
    renderPage();
    const user = userEvent.setup();

    await screen.findByText(/AB123CD/);
    await user.click(screen.getByRole("button", { name: /baja temporal/i }));

    expect(screen.getByRole("button", { name: /procesando/i })).toBeDisabled();

    resolverBaja({ ...vehiculoActivo, estado: "baja_temporal" });

    await waitFor(() => {
      expect(screen.getByText(/baja_temporal/)).toBeInTheDocument();
    });
  });

  it("muestra un mensaje de éxito tras una baja temporal exitosa", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoActivo]);
    bajaTemporal.mockResolvedValueOnce({ ...vehiculoActivo, estado: "baja_temporal" });
    renderPage();
    const user = userEvent.setup();

    await screen.findByText(/AB123CD/);
    await user.click(screen.getByRole("button", { name: /baja temporal/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/éxito/i);
  });

  it("dispara la baja definitiva y actualiza el estado tras el éxito", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoActivo]);
    bajaDefinitiva.mockResolvedValueOnce({ ...vehiculoActivo, estado: "baja_definitiva" });
    renderPage();
    const user = userEvent.setup();

    await screen.findByText(/AB123CD/);
    await user.click(screen.getByRole("button", { name: /baja definitiva/i }));

    await waitFor(() => {
      expect(screen.getByText(/baja_definitiva/)).toBeInTheDocument();
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/éxito/i);
  });

  it("dispara la reactivación y actualiza el estado tras el éxito", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoEnBajaTemporal]);
    reactivarVehiculo.mockResolvedValueOnce({ ...vehiculoEnBajaTemporal, estado: "activo" });
    renderPage();
    const user = userEvent.setup();

    await screen.findByText(/XY999ZZ/);
    await user.click(screen.getByRole("button", { name: /reactivar/i }));

    await waitFor(() => {
      expect(screen.getByText(/XY999ZZ — camioneta — activo/)).toBeInTheDocument();
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/éxito/i);
  });

  it("muestra un mensaje de error si la acción falla", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoActivo]);
    const error = new Error("La operación no es válida para el estado actual.");
    error.status = 409;
    bajaTemporal.mockRejectedValueOnce(error);
    renderPage();
    const user = userEvent.setup();

    await screen.findByText(/AB123CD/);
    await user.click(screen.getByRole("button", { name: /baja temporal/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/operación no es válida/i);
  });

  it("una acción en curso sobre un vehículo no se ve afectada por otra acción distinta en curso sobre otro vehículo", async () => {
    listarVehiculos.mockResolvedValueOnce([vehiculoActivo, vehiculoEnBajaTemporal]);

    let resolverA;
    bajaTemporal.mockReturnValueOnce(
      new Promise((resolve) => {
        resolverA = resolve;
      }),
    );
    let resolverB;
    bajaDefinitiva.mockReturnValueOnce(
      new Promise((resolve) => {
        resolverB = resolve;
      }),
    );

    renderPage();
    const user = userEvent.setup();

    const filas = await screen.findAllByRole("listitem");
    const filaA = filas.find((li) => within(li).queryByText(/AB123CD/));
    const filaB = filas.find((li) => within(li).queryByText(/XY999ZZ/));

    await user.click(within(filaA).getByRole("button", { name: /^baja temporal$/i }));
    // Dispara una acción DISTINTA sobre otro vehículo mientras la primera sigue en vuelo.
    await user.click(within(filaB).getByRole("button", { name: /^baja definitiva$/i }));

    // Ambas acciones deben seguir "en curso" de forma independiente: la
    // acción sobre B no debe apagar el loading de A (regresión del hallazgo
    // de condición de carrera en `accionEnCurso`).
    expect(within(filaA).getByRole("button", { name: /procesando/i })).toBeDisabled();
    expect(within(filaB).getByRole("button", { name: /procesando/i })).toBeDisabled();

    resolverA({ ...vehiculoActivo, estado: "baja_temporal" });
    await waitFor(() => {
      expect(within(filaA).queryByRole("button", { name: /procesando/i })).not.toBeInTheDocument();
    });
    // B sigue en curso: no debió haberse liberado por el `finally` de A.
    expect(within(filaB).getByRole("button", { name: /procesando/i })).toBeDisabled();

    resolverB({ ...vehiculoEnBajaTemporal, estado: "baja_definitiva" });
    await waitFor(() => {
      expect(within(filaB).queryByRole("button", { name: /procesando/i })).not.toBeInTheDocument();
    });
  });
});
