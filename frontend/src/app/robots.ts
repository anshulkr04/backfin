import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      // Google
      {
        userAgent: "Googlebot",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      // Bing / Microsoft Copilot
      {
        userAgent: "Bingbot",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      {
        userAgent: "msnbot",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      // OpenAI / ChatGPT
      {
        userAgent: "GPTBot",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      {
        userAgent: "ChatGPT-User",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      // Perplexity
      {
        userAgent: "PerplexityBot",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      // Anthropic / Claude
      {
        userAgent: "ClaudeBot",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
      {
        userAgent: "anthropic-ai",
        allow: "/",
        disallow: ["/dashboard/", "/auth"],
      },
    ],
    sitemap: "https://marketwire.app/sitemap.xml",
  };
}
