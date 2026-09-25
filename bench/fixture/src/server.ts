import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { defaultConfig } from "./config.js";
import { listWidgets } from "./widgets.js";

const webDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "web");

export function createApp() {
  return createServer(async (req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");

    if (url.pathname === "/config") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(defaultConfig));
      return;
    }

    if (url.pathname === "/widgets") {
      const clientId = url.searchParams.get("clientId") ?? "anonymous";
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(listWidgets(clientId)));
      return;
    }

    const staticPath = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
    try {
      const body = await readFile(path.join(webDir, staticPath));
      const contentType = staticPath.endsWith(".js") ? "text/javascript" : "text/html";
      res.writeHead(200, { "content-type": contentType });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end();
    }
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  createApp().listen(3000);
}
