import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import * as Icons from "./icons";

const NOMBRES_ESPERADOS = [
  "IconAuto",
  "IconClipboard",
  "IconLock",
  "IconArrowLeft",
  "IconLogout",
];

describe("icons", () => {
  it("renderiza cada ícono como un elemento svg", () => {
    NOMBRES_ESPERADOS.forEach((nombre) => {
      const IconComponent = Icons[nombre];
      expect(typeof IconComponent).toBe("function");

      const { container } = render(<IconComponent data-testid={nombre} />);
      const svg = container.querySelector("svg");

      expect(svg).not.toBeNull();
      expect(svg.tagName.toLowerCase()).toBe("svg");
    });
  });
});
