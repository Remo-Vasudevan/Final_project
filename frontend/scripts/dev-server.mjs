import http from "node:http";
import { createReadStream, existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, "..");

const args = process.argv.slice(2);
const readFlag = (flag, fallback) => {
  const index = args.indexOf(flag);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const rootDir = path.resolve(frontendRoot, readFlag("--root", "."));
const port = Number(readFlag("--port", process.env.FRONTEND_PORT || 4173));
const apiOrigin = process.env.API_ORIGIN || "http://127.0.0.1:8001";
const proxyPrefixes = ["/upload", "/health", "/docs", "/openapi.json", "/outputs", "/uploads", "/report", "/favicon.ico"];

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".bmp": "image/bmp",
  ".tif": "image/tiff",
  ".tiff": "image/tiff",
  ".svg": "image/svg+xml",
};

function shouldProxy(urlPath) {
  return proxyPrefixes.some((prefix) => urlPath === prefix || urlPath.startsWith(`${prefix}/`));
}

function proxyRequest(clientReq, clientRes) {
  const target = new URL(clientReq.url, apiOrigin);
  const requestOptions = {
    hostname: target.hostname,
    port: target.port,
    path: `${target.pathname}${target.search}`,
    method: clientReq.method,
    headers: {
      ...clientReq.headers,
      host: target.host,
    },
  };

  const proxyReq = http.request(requestOptions, (proxyRes) => {
    clientRes.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
    proxyRes.pipe(clientRes, { end: true });
  });

  proxyReq.on("error", (error) => {
    clientRes.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    clientRes.end(JSON.stringify({ detail: `Backend proxy error: ${error.message}` }));
  });

  clientReq.pipe(proxyReq, { end: true });
}

function sendFile(filePath, response) {
  const extension = path.extname(filePath).toLowerCase();
  response.writeHead(200, { "Content-Type": mimeTypes[extension] || "application/octet-stream" });
  createReadStream(filePath).pipe(response);
}

const server = http.createServer(async (request, response) => {
  if (!request.url) {
    response.writeHead(400);
    response.end("Bad request");
    return;
  }

  const url = new URL(request.url, `http://127.0.0.1:${port}`);

  if (shouldProxy(url.pathname)) {
    proxyRequest(request, response);
    return;
  }

  let filePath = path.join(rootDir, decodeURIComponent(url.pathname));
  if (url.pathname === "/") {
    filePath = path.join(rootDir, "index.html");
  }

  if (!existsSync(filePath)) {
    filePath = path.join(rootDir, "index.html");
  }

  try {
    if (path.basename(filePath) === "index.html") {
      const html = await readFile(filePath, "utf8");
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end(html);
      return;
    }

    sendFile(filePath, response);
  } catch (error) {
    response.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
    response.end(JSON.stringify({ detail: `Frontend server error: ${error.message}` }));
  }
});

server.listen(port, "127.0.0.1");
