import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Locks the exact manifest.json shape webapp-spec S7 requires — name,
// standalone display, theme/background colors, and both icon sizes.
// webapp-spec S7이 요구하는 manifest.json의 정확한 모양을 고정 —
// name·standalone display·theme/background 색·아이콘 두 사이즈.
describe("public/manifest.json", () => {
  it("matches the required S7 fields", () => {
    const raw = readFileSync(path.resolve(__dirname, "../../public/manifest.json"), "utf-8");
    const manifest = JSON.parse(raw);

    expect(manifest).toEqual({
      name: "Dajung AI",
      short_name: "Dajung AI",
      start_url: "/",
      display: "standalone",
      background_color: "#FFF5DA",
      theme_color: "#422A1E",
      icons: [
        { src: "/icons/mascot-192.png", sizes: "192x192", type: "image/png" },
        { src: "/icons/mascot-512.png", sizes: "512x512", type: "image/png" },
      ],
    });
  });
});
