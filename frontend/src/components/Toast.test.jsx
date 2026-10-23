import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Toast } from "./Toast";

describe("Toast", () => {
  it("shows the notice on screen, in a live region, with a dismiss button", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<Toast notice="That was the last track in the list." onDismiss={onDismiss} />);

    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("That was the last track in the list.");
    expect(region.querySelector(".toast")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalled();
  });

  it("renders nothing visible without a notice, but keeps the live region", () => {
    render(<Toast notice="" onDismiss={() => {}} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
