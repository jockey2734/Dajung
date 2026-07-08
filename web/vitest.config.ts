import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    // Without this, Vite resolves "next/server" (pulled in transitively by
    // `next-auth`) under browser export conditions and fails to find it —
    // it's a Node-only export, and vitest runs under Node regardless of the
    // jsdom test environment.
    // 이게 없으면 Vite가 (`next-auth`가 끌어오는) "next/server"를 browser
    // export 조건으로 찾다가 실패한다 — Node 전용 export라서, jsdom
    // 테스트 환경과 무관하게 vitest 자체는 Node 위에서 돈다.
    conditions: ["node"],
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
});
