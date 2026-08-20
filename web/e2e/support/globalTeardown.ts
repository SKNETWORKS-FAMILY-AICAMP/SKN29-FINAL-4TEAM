import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { sanitizeArtifactTree } from "./artifactSanitizer.js";

const SUPPORT_DIR = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(SUPPORT_DIR, "../..");
const ARTIFACT_ROOT = resolve(WEB_ROOT, ".runtime/playwright");

export default function globalTeardown(): void {
  if (!existsSync(ARTIFACT_ROOT)) return;
  sanitizeArtifactTree(ARTIFACT_ROOT);
}
