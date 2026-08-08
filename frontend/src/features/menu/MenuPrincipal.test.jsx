import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MenuPrincipal from "./MenuPrincipal";

describe("MenuPrincipal", () => {
  it("renderiza las 3 opciones con su texto", () => {
    render(<MenuPrincipal onSelect={() => {}} />);

    expect(screen.getByText("Administrador")).toBeInTheDocument();
    expect(screen.getByText("Gestionar reservas")).toBeInTheDocument();
    expect(screen.getByText("Consultar")).toBeInTheDocument();
  });

  it('click en "Consultar" llama a onSelect con "consultar"', async () => {
    const onSelect = vi.fn();
    render(<MenuPrincipal onSelect={onSelect} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /consultar/i }));

    expect(onSelect).toHaveBeenCalledWith("consultar");
  });

  it('click en "Gestionar reservas" llama a onSelect con "gestionar"', async () => {
    const onSelect = vi.fn();
    render(<MenuPrincipal onSelect={onSelect} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /gestionar reservas/i }));

    expect(onSelect).toHaveBeenCalledWith("gestionar");
  });

  it('click en "Administrador" llama a onSelect con "admin"', async () => {
    const onSelect = vi.fn();
    render(<MenuPrincipal onSelect={onSelect} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /administrador/i }));

    expect(onSelect).toHaveBeenCalledWith("admin");
  });
});
