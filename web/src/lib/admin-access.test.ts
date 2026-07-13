import { describe, expect, it } from "vitest";
import { canAccessAdmin, resolveAppGate } from "./admin-access";

describe("canAccessAdmin (webapp-spec S20 staff guard)", () => {
  it("allows owner and president, denies staff", () => {
    expect(canAccessAdmin("owner")).toBe(true);
    expect(canAccessAdmin("president")).toBe(true);
    expect(canAccessAdmin("staff")).toBe(false);
  });
});

describe("resolveAppGate (webapp-spec S20 forced password change)", () => {
  it("forces /password while must_change_password is set", () => {
    expect(resolveAppGate({ role: "staff", must_change_password: true })).toBe("/password");
    expect(resolveAppGate({ role: "owner", must_change_password: true })).toBe("/password");
  });

  it("lets normal accounts and missing me through", () => {
    expect(resolveAppGate({ role: "staff", must_change_password: false })).toBeNull();
    expect(resolveAppGate(null)).toBeNull();
  });
});
