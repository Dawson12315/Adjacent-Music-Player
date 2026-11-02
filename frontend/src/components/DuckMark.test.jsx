import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DuckMark } from "./DuckMark";
import { ThemeContext } from "../contexts/ThemeContext";
import { DRESS_IDS } from "../theme/themes";

describe("the duck's dress", () => {
  it("wears nothing by default, and what the theme says otherwise", () => {
    const bare = render(<DuckMark />);
    expect(bare.container.querySelector("[data-dress]")).toBeNull();

    const dressed = render(
      <ThemeContext.Provider value={{ dress: "santa" }}>
        <DuckMark tile />
      </ThemeContext.Provider>,
    );
    expect(dressed.container.querySelector("[data-dress='santa']")).not.toBeNull();
  });

  it("takes a dress by prop over the theme, and knows all eight", () => {
    const { container } = render(
      <ThemeContext.Provider value={{ dress: "santa" }}>
        <DuckMark dress="witch" />
      </ThemeContext.Provider>,
    );
    expect(container.querySelector("[data-dress='witch']")).not.toBeNull();
    for (const dress of DRESS_IDS) {
      const one = render(<DuckMark dress={dress} />);
      expect(one.container.querySelector(`[data-dress='${dress}']`), dress).not.toBeNull();
    }
    const none = render(<DuckMark dress={null} />);
    expect(none.container.querySelector("[data-dress]")).toBeNull();
  });
});

describe("the duck's outline", () => {
  it("has none unless asked, and a thin dark one underneath when it is", () => {
    const { container, rerender } = render(<DuckMark />);
    expect(container.querySelector("[data-outline]")).toBeNull();
    rerender(<DuckMark outline />);
    const line = container.querySelector("[data-outline]");
    expect(line).not.toBeNull();
    expect(Number(line.getAttribute("stroke-width"))).toBeLessThan(2);
    // Under the bird, never over it: the outline group comes first.
    const group = line.parentElement;
    expect(group.firstElementChild).toBe(line);
    expect(line.querySelectorAll("path, circle")).toHaveLength(4);
  });
});
