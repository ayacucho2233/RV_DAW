import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReservaForm from "./ReservaForm";
import { crearReserva } from "./reservasApi";

vi.mock("./reservasApi", () => ({
  crearReserva: vi.fn(),
}));

const vehiculos = [{ vehiculo_id: 1, patente: "AB123CD", tipo: "auto" }];

function setFecha(input, value) {
  fireEvent.change(input, { target: { value } });
}

async function completarCamposObligatorios(user, { fechaInicio = "2026-08-10T10:00", fechaFin = "2026-08-10T12:00" } = {}) {
  await user.type(screen.getByLabelText(/nombre/i), "Juan Pérez");
  await user.type(screen.getByLabelText(/legajo/i), "1234");
  await user.type(screen.getByLabelText(/licencia/i), "5678");
  setFecha(screen.getByLabelText(/inicio/i), fechaInicio);
  setFecha(screen.getByLabelText(/fin/i), fechaFin);
  await user.type(screen.getByLabelText(/destino/i), "Sucursal Norte");
}

describe("ReservaForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no envía la request si falta un campo obligatorio", async () => {
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    // Solo completa el nombre, deja el resto vacío.
    await user.type(screen.getByLabelText(/nombre/i), "Juan Pérez");
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    expect(crearReserva).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/obligatorio/i);
  });

  it("no envía la request si fecha_fin es anterior o igual a fecha_inicio", async () => {
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await completarCamposObligatorios(user, {
      fechaInicio: "2026-08-10T10:00",
      fechaFin: "2026-08-10T09:00",
    });
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    expect(crearReserva).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/posterior/i);
  });

  it("muestra un mensaje de éxito tras crear la reserva (201)", async () => {
    crearReserva.mockResolvedValueOnce({
      id: 1,
      vehiculo_id: 1,
      nombre_empleado: "Juan Pérez",
      legajo: "1234",
      licencia: "5678",
      fecha_inicio: "2026-08-10T13:00:00Z",
      fecha_fin: "2026-08-10T15:00:00Z",
      destino: "Sucursal Norte",
      estado: "activa",
    });
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await completarCamposObligatorios(user);
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/éxito/i);
    expect(crearReserva).toHaveBeenCalledTimes(1);
  });

  it("muestra un mensaje de error ante un 404 del backend (vehículo inexistente)", async () => {
    const error = new Error("No se encontró el vehículo con id 1.");
    error.status = 404;
    error.detail = "No se encontró el vehículo con id 1.";
    crearReserva.mockRejectedValueOnce(error);
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await completarCamposObligatorios(user);
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/vehículo/i);
  });

  it("muestra un mensaje de error ante un 409 por solapamiento de reservas", async () => {
    const error = new Error("Ya existe una reserva activa que se superpone para el vehículo 1.");
    error.status = 409;
    error.detail = "Ya existe una reserva activa que se superpone para el vehículo 1.";
    crearReserva.mockRejectedValueOnce(error);
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await completarCamposObligatorios(user);
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/superpone|ocupado|ya.*reservado/i);
  });

  it("muestra un mensaje de error ante un 409 por vehículo no activo, distinto del de solapamiento", async () => {
    const error = new Error(
      "El vehículo con id 1 no está disponible para reservas (estado actual: 'baja_temporal').",
    );
    error.status = 409;
    error.detail =
      "El vehículo con id 1 no está disponible para reservas (estado actual: 'baja_temporal').";
    crearReserva.mockRejectedValueOnce(error);
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await completarCamposObligatorios(user);
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(/no está disponible|dado de baja/i);
    expect(alerta).not.toHaveTextContent(/superpone/i);
  });

  it("muestra un mensaje de error ante un 422 del backend", async () => {
    const error = new Error("Error de validación");
    error.status = 422;
    error.detail = [{ msg: "fecha_fin debe ser posterior a fecha_inicio" }];
    crearReserva.mockRejectedValueOnce(error);
    render(<ReservaForm vehiculos={vehiculos} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await completarCamposObligatorios(user);
    await user.click(screen.getByRole("button", { name: /reservar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/datos|válid/i);
  });
});
