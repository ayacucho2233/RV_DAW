import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { useSession } from "./context/SessionContext";

// Mock del cliente HTTP: capturamos el handler de 401 registrado por App.jsx
// para poder simularlo desde el test, sin depender de una llamada real a la
// API (App.test.jsx se mantiene aislado, igual que los mocks de los 4
// componentes reutilizados de abajo).
const { setAuthSessionMock, setUnauthorizedHandlerMock, unauthorizedHandlerRef, postMock } = vi.hoisted(() => {
  const ref = { current: null };
  return {
    setAuthSessionMock: vi.fn(),
    setUnauthorizedHandlerMock: vi.fn((handler) => {
      ref.current = handler;
    }),
    unauthorizedHandlerRef: ref,
    // El useEffect nuevo de App.jsx (FEAT-005, Block 4) llama a
    // caducarReservasVencidas(), que a su vez llama a apiClient.post (el
    // `default` de client.js) vía reservasApi.js — sin este mock, cualquier
    // test que monte <App/> revienta con "Cannot read properties of
    // undefined (reading 'post')".
    postMock: vi.fn().mockResolvedValue({ data: { caducadas: 0 } }),
  };
});

vi.mock("./api/client", () => ({
  setAuthSession: setAuthSessionMock,
  setUnauthorizedHandler: setUnauthorizedHandlerMock,
  default: { post: postMock },
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

  it("llama a caducarReservasVencidas una vez al montar", async () => {
    // Mockeamos reservasApi.js directamente (en vez de ./api/client, usado
    // por el resto de la suite) para aislar este assert de la
    // implementación interna de caducarReservasVencidas — spec Block 4 de
    // FEAT-005. vi.resetModules()+import() dinámico es necesario porque
    // App ya fue importado estáticamente arriba con el mock de ./api/client
    // vigente para el resto de los tests.
    vi.resetModules();
    const caducarReservasVencidasMock = vi.fn().mockResolvedValue({ caducadas: 0 });
    vi.doMock("./features/reservas/reservasApi", () => ({
      caducarReservasVencidas: caducarReservasVencidasMock,
    }));

    const { default: AppConMockDirecto } = await import("./App");
    render(<AppConMockDirecto />);

    expect(caducarReservasVencidasMock).toHaveBeenCalledTimes(1);

    vi.doUnmock("./features/reservas/reservasApi");
    vi.resetModules();
  });

  it("no falla si caducarReservasVencidas rechaza", async () => {
    postMock.mockRejectedValueOnce(new Error("Network Error"));

    render(<App />);

    // Confirma que el efecto realmente se disparó (y que su promesa fue la
    // que rechazó) antes de verificar que la app sigue en pie — si no, el
    // test pasaría trivialmente incluso sin el useEffect implementado.
    await vi.waitFor(() => expect(postMock).toHaveBeenCalled());

    expect(screen.getByRole("button", { name: /consultar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /gestionar reservas/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Administrador" })).toBeInTheDocument();
  });
});
