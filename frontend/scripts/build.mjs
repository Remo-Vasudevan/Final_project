import { mkdir, cp, readFile, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");
const distRoot = path.join(frontendRoot, "dist");
const indexPath = path.join(frontendRoot, "index.html");
const distIndexPath = path.join(distRoot, "index.html");
const staticSource = path.join(frontendRoot, "static");
const staticTarget = path.join(distRoot, "static");

await rm(distRoot, { recursive: true, force: true });
await mkdir(distRoot, { recursive: true });
await cp(staticSource, staticTarget, { recursive: true });

const html = await readFile(indexPath, "utf8");
await writeFile(distIndexPath, html, "utf8");
