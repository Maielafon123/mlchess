import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const target = process.env.MLCHESS_DEV_API_TARGET;
if (target && !/^http:\/\/(127\.0\.0\.1|localhost):[0-9]{1,5}$/.test(target)) throw new Error("Development API proxy must use an explicit loopback address");
const proxy = target ? { "/api": { target }, "/ws": { target, ws: true } } : undefined;
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 4173, strictPort: true, proxy },
});
