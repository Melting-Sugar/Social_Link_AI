import fs from "node:fs";
import path from "node:path";

/**
 * `process.cwd()` for the Next.js server process varies by how it's
 * launched — `frontend/` when run via `npm run dev` from inside that
 * directory, but the repo root when launched with `next dev <dir>` from
 * one level up (as this project's dev-preview tooling does). Try both
 * rather than assuming one.
 */
export function readLegalDoc(filename: string): string {
  const candidates = [
    path.join(process.cwd(), "docs", "legal", filename),
    path.join(process.cwd(), "..", "docs", "legal", filename),
  ];
  const found = candidates.find((p) => fs.existsSync(p));
  if (!found) {
    throw new Error(`Could not locate docs/legal/${filename} from cwd=${process.cwd()}`);
  }
  return fs.readFileSync(found, "utf-8");
}
