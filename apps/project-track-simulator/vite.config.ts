import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8010";
const uiPort = Number(process.env.UI_PORT ?? process.env.PORT ?? 5175);

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: uiPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
      "/health": {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});