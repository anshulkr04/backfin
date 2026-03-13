import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import cloudflare from "@astrojs/cloudflare";

export default defineConfig({
  site: "https://news.marketwire.app",
  integrations: [
    tailwind(),
  ],
  output: "hybrid",
  adapter: cloudflare(),
  build: {
    format: "directory",
  },
});
