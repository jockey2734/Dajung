import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PantryCardList } from "./pantry-card-list";
import type { PantryItemOut } from "@/types/pantry";

afterEach(() => {
  cleanup();
});

const items: PantryItemOut[] = [
  {
    id: "1",
    name: "케냐 AA",
    kind: "coffee",
    remaining_pct: 75,
    capacity_g: 200,
    estimated_g: 150,
    note: null,
    updated_by: { id: "u1", name: "운하" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function renderList(order: "asc" | "desc", onSortChange = vi.fn()) {
  return render(
    <PantryCardList
      items={items}
      sort="updated_at"
      order={order}
      onSortChange={onSortChange}
      onUpdate={vi.fn()}
      onDelete={vi.fn()}
      onAdd={vi.fn()}
    />,
  );
}

describe("PantryCardList sort toggle (webapp-spec S17)", () => {
  it("calls onSortChange with the currently active sort field on click", async () => {
    const user = userEvent.setup();
    const onSortChange = vi.fn();
    renderList("desc", onSortChange);

    await user.click(screen.getByRole("button", { name: /내림차순/ }));
    expect(onSortChange).toHaveBeenCalledWith("updated_at");
  });

  it("shows a down arrow when order is desc and an up arrow when order is asc", () => {
    const { rerender } = renderList("desc");
    expect(screen.getByRole("button", { name: /내림차순/ })).toBeInTheDocument();

    rerender(
      <PantryCardList
        items={items}
        sort="updated_at"
        order="asc"
        onSortChange={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onAdd={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /오름차순/ })).toBeInTheDocument();
  });
});
