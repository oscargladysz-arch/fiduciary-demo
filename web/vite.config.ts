import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" so the same build serves the gh-pages root, a pull request
// preview under previews/<n>/ and the workspace API's static mount.
// TARK_ADAPTER picks the data adapter at build time (static | api).
export default defineConfig({
  base: "./",
  plugins: [react()],
  define: {
    __TARK_ADAPTER__: JSON.stringify(process.env.TARK_ADAPTER || "static"),
    __TARK_API_BASE__: JSON.stringify(process.env.TARK_API_BASE || "/api"),
  },
  build: {
    outDir: process.env.TARK_WEB_OUT || "../site_next",
    emptyOutDir: true,
    sourcemap: false,
    target: "es2020",
    modulePreload: { polyfill: false },
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react") || id.includes("node_modules/scheduler")) return "react";
          if (id.includes("node_modules/@tanstack")) return "table";
          return undefined;
        },
      },
    },
  },
  server: { port: 5173, strictPort: true },
});
