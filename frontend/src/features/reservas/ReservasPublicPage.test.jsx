import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReservasPublicPage from "./ReservasPublicPage";
import { listarVehiculosPool, consultarDisponibilidad, crearReserva } from "./reservasApi";

vi.mock("./reservasApi", () => ({
  listarVehiculosPool: vi.fn(),
  consultarDisponibilidad: vi.fn(),
  crearReserva: vi.fn(),
}));

function setFecha(input, value) {
  fireEvent.change(input, { target: { value } });
}

async function consultarDisponibilidadUI(user) {
  setFecha(screen.getByLabelText(/desde/i), "2026-08-10T10:00");
  setFecha(screen.getByLabelText(/hasta/i), "2026-08-10T12:00");
  await user.click(screen.getByRole("button", { name: /consultar disponibilidad/i }));
}

describe("ReservasPublicPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza la lista de vehículos desde GET /reservas/vehiculos", async () => {
    listarVehiculosPool.mockResolvedValueOnce([{ patente: "AB123CD", tipo: "auto" }]);
    render(<ReservasPublicPage />);

    expect(await screen.findByText(/AB123CD/)).toBeInTheDocument();
  });

  it("consulta disponibilidad y refleja disponible/no disponible por vehículo", async () => {
    listarVehiculosPool.mockResolvedValueOnce([]);
    consultarDisponibilidad.mockResolvedValueOnce([
      { vehiculo_id: 1, patente: "AB123CD", tipo: "auto", disponible: true },
      { vehiculo_id: 2, patente: "XY999ZZ", tipo: "camioneta", disponible: false },
    ]);
    render(<ReservasPublicPage />);
    const user = userEvent.setup();

    await consultarDisponibilidadUI(user);

    const filaDisponible = await screen.findByText(/AB123CD/);
    expect(filaDisponible.closest("li")).toHaveTextContent(/disponible/i);
    const filaNoDisponible = await screen.findByText(/XY999ZZ/);
    expect(filaNoDisponible.closest("li")).toHaveTextContent(/no disponible/i);

    expect(consultarDisponibilidad).toHaveBeenCalledTimes(1);
  });

  it("abre ReservaForm con el vehículo elegido tras consultar disponibilidad", async () => {
    listarVehiculosPool.mockResolvedValueOnce([]);
    consultarDisponibilidad.mockResolvedValueOnce([
      { vehiculo_id: 1, patente: "AB123CD", tipo: "auto", disponible: true },
    ]);
    render(<ReservasPublicPage />);
    const user = userEvent.setup();

    await consultarDisponibilidadUI(user);
    await screen.findByText(/AB123CD/);
    await user.click(screen.getByRole("button", { name: /^reservar$/i }));

    const form = await screen.findByRole("form", { name: /reservar vehículo/i });
    expect(form).toBeInTheDocument();
    expect(screen.getByLabelText("Vehículo")).toHaveValue("1");
  });
});
