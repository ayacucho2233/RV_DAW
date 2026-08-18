import { describe, it, expect, vi, beforeEach } from "vitest";
import apiClient from "../../api/client";
import { caducarReservasVencidas } from "./reservasApi";

// Mismo patrón de mock que usan los componentes que consumen reservasApi.js
// (ConsultaPorPatente.test.jsx, ReservaForm.test.jsx, etc.), pero acá se
// mockea un nivel más abajo (`api/client`) porque lo que se está probando es
// justamente reservasApi.js — Block 4, spec FEAT-005.
vi.mock("../../api/client", () => ({
  default: { post: vi.fn() },
}));

describe("caducarReservasVencidas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("llama a POST /reservas/caducar-vencidas y devuelve data", async () => {
    apiClient.post.mockResolvedValue({ data: { caducadas: 3 } });

    const resultado = await caducarReservasVencidas();

    expect(apiClient.post).toHaveBeenCalledWith("/reservas/caducar-vencidas");
    expect(resultado).toEqual({ caducadas: 3 });
  });

  it("propaga error tipado ante fallo de red", async () => {
    apiClient.post.mockRejectedValue(new Error("Network Error"));

    await expect(caducarReservasVencidas()).rejects.toMatchObject({
      message: "No se pudo conectar con el servidor.",
      status: null,
      detail: null,
    });
  });
});
