// content/legal/*.md is bundled in as a raw string at build time (via
// Turbopack's raw-loader compat — see next.config.ts docs on `with {
// turbopackLoader }`) rather than read from disk at request time. An
// `fs.readFileSync` lookup worked for a plain Node.js server but broke on
// Cloudflare Workers: confirmed by an actual OpenNext Cloudflare build +
// local wrangler run, `process.cwd()` resolves to an internal `/bundle`
// path there with no real filesystem behind it, so any runtime path-based
// lookup fails regardless of what path it computes. Bundling the content
// in at build time sidesteps the whole problem — by the time the code
// runs, the text is already just a JS string, on every target.
import privacyPolicy from "@/content/legal/privacy-policy.md" with {
  turbopackLoader: "raw-loader",
  turbopackAs: "*.js",
};
import termsOfService from "@/content/legal/terms-of-service.md" with {
  turbopackLoader: "raw-loader",
  turbopackAs: "*.js",
};

const DOCS = {
  "terms-of-service.md": termsOfService,
  "privacy-policy.md": privacyPolicy,
} as const;

export function readLegalDoc(filename: keyof typeof DOCS): string {
  return DOCS[filename];
}
