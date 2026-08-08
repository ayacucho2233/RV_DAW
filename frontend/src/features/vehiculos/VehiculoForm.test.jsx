import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VehiculoForm from "./VehiculoForm";
import { crearVehiculo, modificarVehiculo } from "./vehiculosApi";

vi.mock("./vehiculosApi", () => ({
  crearVehiculo: vi.fn(),
  modificarVehiculo: vi.fn(),
}));

describe("VehiculoForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no envía la request si falta la patente", async () => {
    render(<VehiculoForm onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(crearVehiculo).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/patente.*obligatoria/i);
  });

  it("el campo tipo solo permite los dos valores permitidos (auto/camioneta)", () => {
    render(<VehiculoForm onSuccess={vi.fn()} />);
    const select = screen.getByLabelText(/tipo/i);
    const opciones = Array.from(select.querySelectorAll("option")).map((o) => o.value);
    expect(opciones).toEqual(["auto", "camioneta"]);
  });

  it("muestra el error del backend si la request de alta falla", async () => {
    const error = new Error("Ya existe un vehículo con esa patente.");
    error.status = 409;
    crearVehiculo.mockRejectedValueOnce(error);
    render(<VehiculoForm onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/patente/i), "AB123CD");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/ya existe un vehículo/i);
  });

  it("muestra un mensaje de éxito tras crear un vehículo", async () => {
    crearVehiculo.mockResolvedValueOnce({
      id: 5,
      patente: "AB123CD",
      tipo: "auto",
      estado: "activo",
    });
    render(<VehiculoForm onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/patente/i), "AB123CD");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/creado con éxito/i);
  });

  it("muestra un mensaje de éxito tras editar un vehículo", async () => {
    const vehiculo = { id: 7, patente: "XY999ZZ", tipo: "camioneta", estado: "activo" };
    modificarVehiculo.mockResolvedValueOnce({ ...vehiculo, patente: "NEW111" });
    render(<VehiculoForm vehiculo={vehiculo} onSuccess={vi.fn()} />);
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText(/patente/i));
    await user.type(screen.getByLabelText(/patente/i), "NEW111");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(/actualizado con éxito/i);
  });

  it("en edición, llama a modificarVehiculo con el id del vehículo", async () => {
    const vehiculo = {
      id: 7,
      patente: "XY999ZZ",
      tipo: "camioneta",
      estado: "activo",
    };
    modificarVehiculo.mockResolvedValueOnce({ ...vehiculo, patente: "NEW111" });
    const onSuccess = vi.fn();
    render(<VehiculoForm vehiculo={vehiculo} onSuccess={onSuccess} />);
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText(/patente/i));
    await user.type(screen.getByLabelText(/patente/i), "NEW111");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(modificarVehiculo).toHaveBeenCalledWith(7, { patente: "NEW111", tipo: "camioneta" });
  });
});
