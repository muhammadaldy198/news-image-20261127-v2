// news-image-20261127 v2 — entrypoint (Kirana, Hunter Office).
// Copies the pre-rendered front page into the grader's output directory.
// The image is drawn at build time by draw.py; this program only ships it.
import { copyFileSync, existsSync, mkdirSync, chmodSync, statSync } from "node:fs";
import { join } from "node:path";

const here = import.meta.dirname;
const source = join(here, "entry.png");
const targetDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";
const target = join(targetDir, "entry.png");

if (!existsSync(source)) {
  throw new Error("entry.png is missing next to main.ts");
}
mkdirSync(targetDir, { recursive: true });
copyFileSync(source, target);
chmodSync(target, 0o644);
const copied = statSync(target).size;
const original = statSync(source).size;
if (copied !== original) {
  throw new Error("copy size mismatch: " + copied + " vs " + original);
}
console.log("news-image-20261127 v2: entry.png -> " + target);
console.log("news-image-20261127 v2: " + copied + " bytes, deterministic copy");
