import { defineConfig } from "vitepress";

export default defineConfig({
  title: "SimpleFlow SDKs",
  description: "Go, Python, and Node SDKs for SimpleFlow runtime integration and telemetry",
  cleanUrls: true,
  lastUpdated: true,
  base: "/",
  themeConfig: {
    nav: [
      { text: "Home", link: "/" },
      { text: "Quick Start", link: "/quickstart" },
      { text: "Agent Integration", link: "/agent-integration" },
      { text: "Telemetry", link: "/telemetry-envelope-v1" }
    ],
    sidebar: [
      {
        text: "Get Started",
        items: [
          { text: "Overview", link: "/" },
          { text: "Quick Start", link: "/quickstart" },
          { text: "Agent Integration", link: "/agent-integration" }
        ]
      },
      {
        text: "SDK Guides",
        items: [
          { text: "Node SDK", link: "/sdk-node" },
          { text: "Python SDK", link: "/sdk-python" },
          { text: "Go SDK", link: "/sdk-go" }
        ]
      },
      {
        text: "Telemetry and Ops",
        items: [
          { text: "Telemetry Envelope V1", link: "/telemetry-envelope-v1" },
          { text: "Publishing", link: "/publishing" },
          { text: "Troubleshooting", link: "/troubleshooting" }
        ]
      }
    ],
    search: { provider: "local" },
    editLink: {
      pattern: "https://github.com/CraftsMan-Labs/SimpleFlowSDKs/edit/main/docs/:path",
      text: "Suggest edits"
    },
    socialLinks: [{ icon: "github", link: "https://github.com/CraftsMan-Labs/SimpleFlowSDKs" }],
    footer: {
      message: "Released under the Apache-2.0 License.",
      copyright: "Copyright © CraftsMan Labs"
    }
  },
  markdown: { lineNumbers: true },
  sitemap: { hostname: "https://docs.simpleflow-sdk.craftsmanlabs.net" }
});
