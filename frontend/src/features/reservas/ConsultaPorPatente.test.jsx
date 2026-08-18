import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConsultaPorPatente from "./ConsultaPorPatente";
import { consultarReservasActivasPorVehiculo } from "./reservasApi";

vi.mock("./reservasApi", () => ({
  consultarReservasActivasPorVehiculo: vi.fn(),
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

async function buscarPatente(user, patente = "AB123CD") {
  await user.type(screen.getByLabelText(/patente/i), patente);
  await user.click(screen.getByRole("button", { name: /buscar/i }));
}

describe("ConsultaPorPatente", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza el formulario de búsqueda", () => {
    render(<ConsultaPorPatente />);

    expect(screen.getByLabelText(/patente/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /buscar/i })).toBeInTheDocument();
  });

  it("busca y muestra reservas activas al enviar una patente con resultados", async () => {
    consultarReservasActivasPorVehiculo.mockResolvedValueOnce([reservaActiva]);
    render(<ConsultaPorPatente />);
    const user = userEvent.setup();

    await buscarPatente(user);

    expect(consultarReservasActivasPorVehiculo).toHaveBeenCalledWith("AB123CD");
    expect(await screen.findByText(/Juan Pérez/)).toBeInTheDocument();
    expect(screen.getByText(/Sucursal Norte/)).toBeInTheDocument();
  });

  it('muestra mensaje de "sin reservas activas" cuando la respuesta es una lista vacía', async () => {
    consultarReservasActivasPorVehiculo.mockResolvedValueOnce([]);
    render(<ConsultaPorPatente />);
    const user = userEvent.setup();

    await buscarPatente(user);

    expect(await screen.findByRole("status")).toHaveTextContent(/no tiene reservas activas/i);
  });

  it("muestra mensaje de error cuando la patente no existe (404)", async () => {
    const error = new Error("No se encontró el vehículo con patente 'ZZZ999'.");
    error.status = 404;
    error.detail = "No se encontró el vehículo con patente 'ZZZ999'.";
    consultarReservasActivasPorVehiculo.mockRejectedValueOnce(error);
    render(<ConsultaPorPatente />);
    const user = userEvent.setup();

    await buscarPatente(user, "ZZZ999");

    expect(await screen.findByRole("alert")).toHaveTextContent(/no se encontró ningún vehículo/i);
  });

  it("no llama a la API antes de que el usuario envíe el formulario", async () => {
    render(<ConsultaPorPatente />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/patente/i), "AB123CD");

    expect(consultarReservasActivasPorVehiculo).not.toHaveBeenCalled();
  });

  it("muestra mensaje de rate limit cuando la API responde 429", async () => {
    const error = new Error("Demasiadas solicitudes.");
    error.status = 429;
    error.detail = null;
    consultarReservasActivasPorVehiculo.mockRejectedValueOnce(error);
    render(<ConsultaPorPatente />);
    const user = userEvent.setup();

    await buscarPatente(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /demasiadas solicitudes\. esperá unos minutos e intentá de nuevo\./i,
    );
  });
});
