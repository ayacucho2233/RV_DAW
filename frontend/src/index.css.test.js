import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CSS_PATH = path.join(__dirname, "index.css");

const VARIABLES_ESPERADAS = [
  "--color-primary",
  "--color-primary-hover",
  "--color-accent",
  "--color-success",
  "--color-error",
  "--color-bg",
  "--color-surface",
  "--color-text",
  "--color-text-muted",
  "--color-border",
];

describe("index.css", () => {
  it("define las 10 variables de la paleta dentro de :root", () => {
    const contenido = fs.readFileSync(CSS_PATH, "utf-8");

    const matchRoot = contenido.match(/:root\s*{([^}]*)}/);
    expect(matchRoot).not.toBeNull();
    const bloqueRoot = matchRoot[1];

    VARIABLES_ESPERADAS.forEach((variable) => {
      const regex = new RegExp(`${variable}\\s*:\\s*[^;]+;`);
      expect(bloqueRoot).toMatch(regex);
    });
  });
});
