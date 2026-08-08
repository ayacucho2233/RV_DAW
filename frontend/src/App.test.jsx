import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { useSession } from "./context/SessionContext";

// Mock del cliente HTTP: capturamos el handler de 401 registrado por App.jsx
// para poder simularlo desde el test, sin depender de una llamada real a la
// API (App.test.jsx se mantiene aislado, igual que los mocks de los 4
// componentes reutilizados de abajo).
const { setAuthSessionMock, setUnauthorizedHandlerMock, unauthorizedHandlerRef } = vi.hoisted(() => {
  const ref = { current: null };
  return {
    setAuthSessionMock: vi.fn(),
    setUnauthorizedHandlerMock: vi.fn((handler) => {
      ref.current = handler;
    }),
    unauthorizedHandlerRef: ref,
  };
});

vi.mock("./api/client", () => ({
  setAuthSession: setAuthSessionMock,
  setUnauthorizedHandler: setUnauthorizedHandlerMock,
}));

// Los 4 componentes reutilizados ya tienen su propia cobertura (spec Block 3,
// "Required tests"). Acá se mockean con un marcador simple (`data-testid`)
// para mantener App.test.jsx aislado de su lógica interna.
vi.mock("./features/reservas/ReservasPublicPage", () => ({
  default: () => <div data-testid="reservas-public-page">ReservasPublicPage</div>,
}));

vi.mock("./features/reservas/ReservasListado", () => ({
  default: () => <div data-testid="reservas-listado">ReservasListado</div>,
}));

vi.mock("./features/vehiculos/VehiculosAdminPage", () => ({
  default: () => <div data-testid="vehiculos-admin-page">VehiculosAdminPage</div>,
}));

// El LoginAdmin real se comunica con App.jsx exclusivamente vía
// `useSession().setSession` (ver LoginAdmin.jsx: `const { setSession } =
// useSession();`). Este mock reproduce ese mismo contrato para simular un
// login exitoso desde el test, sin reimplementar el formulario real.
vi.mock("./features/vehiculos/LoginAdmin", () => ({
  default: function LoginAdminMock() {
    const { setSession } = useSession();
    return (
      <div data-testid="login-admin">
        <button
          type="button"
          onClick={() => setSession({ username: "admin", password: "secreto123" })}
        >
          Simular login exitoso
        </button>
      </div>
    );
  },
}));

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    unauthorizedHandlerRef.current = null;
  });

  it("al montar sin sesión, muestra el menú principal", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: /consultar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /gestionar reservas/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Administrador" })).toBeInTheDocument();
    expect(screen.queryByTestId("reservas-public-page")).not.toBeInTheDocument();
    expect(screen.queryByTestId("reservas-listado")).not.toBeInTheDocument();
    expect(screen.queryByTestId("login-admin")).not.toBeInTheDocument();
    expect(screen.queryByTestId("vehiculos-admin-page")).not.toBeInTheDocument();
  });

  it('click en "Consultar" muestra la vista de reservas con botón "Volver al menú"', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /consultar/i }));

    expect(screen.getByTestId("reservas-public-page")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /volver al menú/i })).toBeInTheDocument();
  });

  it('click en "Gestionar reservas" muestra el listado con botón "Volver al menú"', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /gestionar reservas/i }));

    expect(screen.getByTestId("reservas-listado")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /volver al menú/i })).toBeInTheDocument();
  });

  it('click en "Volver al menú" desde Consultar/Gestionar regresa al menú principal', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /consultar/i }));
    expect(screen.getByTestId("reservas-public-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /volver al menú/i }));

    expect(screen.queryByTestId("reservas-public-page")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /consultar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /gestionar reservas/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Administrador" })).toBeInTheDocument();
  });

  it('click en "Administrador" sin sesión muestra el login, con "Volver al menú" y SIN botón "Cerrar sesión"', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Administrador" }));

    expect(screen.getByTestId("login-admin")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /volver al menú/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cerrar sesión/i })).not.toBeInTheDocument();
  });

  it('tras un login exitoso, se muestra el panel admin con "Cerrar sesión" y "Volver al menú" visibles simultáneamente', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Administrador" }));
    await user.click(screen.getByRole("button", { name: /simular login exitoso/i }));

    expect(screen.getByTestId("vehiculos-admin-page")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cerrar sesión/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /volver al menú/i })).toBeInTheDocument();
  });

  it('click en "Cerrar sesión" limpia la sesión y vuelve a mostrar el login (permanece en la rama Administrador, NO salta al menú)', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Administrador" }));
    await user.click(screen.getByRole("button", { name: /simular login exitoso/i }));
    expect(screen.getByTestId("vehiculos-admin-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /cerrar sesión/i }));

    expect(screen.queryByTestId("vehiculos-admin-page")).not.toBeInTheDocument();
    expect(screen.getByTestId("login-admin")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /consultar/i })).not.toBeInTheDocument();
  });

  it('click en "Volver al menú" con sesión activa limpia la sesión Y muestra el menú principal', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Administrador" }));
    await user.click(screen.getByRole("button", { name: /simular login exitoso/i }));
    expect(screen.getByTestId("vehiculos-admin-page")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /volver al menú/i }));

    expect(screen.queryByTestId("vehiculos-admin-page")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /consultar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /gestionar reservas/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Administrador" })).toBeInTheDocument();
  });

  it("un 401 de la API limpia la sesión automáticamente sin romper la navegación", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Administrador" }));
    await user.click(screen.getByRole("button", { name: /simular login exitoso/i }));
    expect(screen.getByTestId("vehiculos-admin-page")).toBeInTheDocument();
    expect(unauthorizedHandlerRef.current).toBeTypeOf("function");

    act(() => {
      unauthorizedHandlerRef.current();
    });

    expect(screen.queryByTestId("vehiculos-admin-page")).not.toBeInTheDocument();
    expect(screen.getByTestId("login-admin")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cerrar sesión/i })).not.toBeInTheDocument();
  });
});
