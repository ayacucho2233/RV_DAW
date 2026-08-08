import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReservasListado from "./ReservasListado";
import { listarReservas, cancelarReserva } from "./reservasApi";

vi.mock("./reservasApi", () => ({
  listarReservas: vi.fn(),
  cancelarReserva: vi.fn(),
}));

const reservaActiva = {
  id: 1,
  vehiculo_id: 10,
  nombre_empleado: "Juan Pérez",
  fecha_inicio: "2026-08-10T13:00:00Z",
  fecha_fin: "2026-08-10T15:00:00Z",
  destino: "Sucursal Norte",
  estado: "activa",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  patente: "AB123CD",
  tipo: "auto",
};

const reservaCancelada = {
  ...reservaActiva,
  id: 2,
  nombre_empleado: "María Gómez",
  estado: "cancelada",
};

function reservaCanceladaDesde(reserva) {
  return { ...reserva, estado: "cancelada" };
}

describe("ReservasListado", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza el listado desde GET /reservas", async () => {
    listarReservas.mockResolvedValueOnce([reservaActiva]);
    render(<ReservasListado />);

    expect(await screen.findByText(/AB123CD/)).toBeInTheDocument();
    expect(screen.getByText(/Juan Pérez/)).toBeInTheDocument();
    expect(screen.getByText(/Sucursal Norte/)).toBeInTheDocument();
    expect(listarReservas).toHaveBeenCalledTimes(1);
    expect(listarReservas).toHaveBeenCalledWith(undefined);
  });

  it("cambiar el filtro dispara una nueva consulta con el período correcto", async () => {
    listarReservas.mockResolvedValue([reservaActiva]);
    render(<ReservasListado />);
    const user = userEvent.setup();

    await screen.findByText(/AB123CD/);
    expect(listarReservas).toHaveBeenCalledTimes(1);

    await user.selectOptions(screen.getByLabelText(/período/i), "futuras");

    expect(listarReservas).toHaveBeenCalledTimes(2);
    expect(listarReservas).toHaveBeenLastCalledWith("futuras");
  });

  it("cancelar con el legajo correcto muestra éxito y refleja estado=cancelada tras refrescar", async () => {
    listarReservas.mockResolvedValueOnce([reservaActiva]);
    listarReservas.mockResolvedValueOnce([reservaCanceladaDesde(reservaActiva)]);
    cancelarReserva.mockResolvedValueOnce({ ...reservaActiva, estado: "cancelada" });
    render(<ReservasListado />);
    const user = userEvent.setup();

    const fila = (await screen.findByText(/AB123CD/)).closest("li");
    await user.click(within(fila).getByRole("button", { name: /cancelar/i }));
    await user.type(within(fila).getByLabelText(/legajo/i), "1234");
    await user.click(within(fila).getByRole("button", { name: /confirmar cancelación/i }));

    expect(cancelarReserva).toHaveBeenCalledWith(1, "1234");
    expect(await screen.findByRole("status")).toBeInTheDocument();
    expect(await within(fila).findByText(/cancelada/i)).toBeInTheDocument();
    expect(listarReservas).toHaveBeenCalledTimes(2);
  });

  it("cancelar con legajo incorrecto muestra el error 403 sin cancelar la reserva", async () => {
    listarReservas.mockResolvedValue([reservaActiva]);
    const error = new Error("El legajo indicado no coincide con el de la reserva.");
    error.status = 403;
    error.detail = "El legajo indicado no coincide con el de la reserva.";
    cancelarReserva.mockRejectedValueOnce(error);
    render(<ReservasListado />);
    const user = userEvent.setup();

    const fila = (await screen.findByText(/AB123CD/)).closest("li");
    await user.click(within(fila).getByRole("button", { name: /cancelar/i }));
    await user.type(within(fila).getByLabelText(/legajo/i), "9999");
    await user.click(within(fila).getByRole("button", { name: /confirmar cancelación/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/legajo/i);
    expect(listarReservas).toHaveBeenCalledTimes(1);
  });

  it("cancelar una reserva ya cancelada muestra el error 409", async () => {
    listarReservas.mockResolvedValue([reservaActiva]);
    const error = new Error("La reserva ya se encuentra cancelada.");
    error.status = 409;
    error.detail = "La reserva ya se encuentra cancelada.";
    cancelarReserva.mockRejectedValueOnce(error);
    render(<ReservasListado />);
    const user = userEvent.setup();

    const fila = (await screen.findByText(/AB123CD/)).closest("li");
    await user.click(within(fila).getByRole("button", { name: /cancelar/i }));
    await user.type(within(fila).getByLabelText(/legajo/i), "1234");
    await user.click(within(fila).getByRole("button", { name: /confirmar cancelación/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/cancelada/i);
  });

  it("cancelar una reserva inexistente (404) muestra el mensaje correspondiente", async () => {
    listarReservas.mockResolvedValue([reservaActiva]);
    const error = new Error("No se encontró la reserva.");
    error.status = 404;
    error.detail = "No se encontró la reserva.";
    cancelarReserva.mockRejectedValueOnce(error);
    render(<ReservasListado />);
    const user = userEvent.setup();

    const fila = (await screen.findByText(/AB123CD/)).closest("li");
    await user.click(within(fila).getByRole("button", { name: /cancelar/i }));
    await user.type(within(fila).getByLabelText(/legajo/i), "1234");
    await user.click(within(fila).getByRole("button", { name: /confirmar cancelación/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no.*existe|no se encontró/i);
  });

  it("no dispara la request si el legajo está vacío", async () => {
    listarReservas.mockResolvedValue([reservaActiva]);
    render(<ReservasListado />);
    const user = userEvent.setup();

    const fila = (await screen.findByText(/AB123CD/)).closest("li");
    await user.click(within(fila).getByRole("button", { name: /cancelar/i }));
    await user.click(within(fila).getByRole("button", { name: /confirmar cancelación/i }));

    expect(cancelarReserva).not.toHaveBeenCalled();
  });
});
