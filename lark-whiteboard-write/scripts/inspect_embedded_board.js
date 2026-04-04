#!/usr/bin/env node

const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

function parseArgs(argv) {
  const options = {
    docUrl: null,
    timeoutMs: 20000,
    waitMs: 8000,
    boardSelector: ".whiteboard-view-container",
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--doc-url":
        options.docUrl = argv[++i];
        break;
      case "--timeout-ms":
        options.timeoutMs = Number(argv[++i]);
        break;
      case "--wait-ms":
        options.waitMs = Number(argv[++i]);
        break;
      case "--board-selector":
        options.boardSelector = argv[++i];
        break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!Number.isFinite(options.timeoutMs) || options.timeoutMs <= 0) {
    throw new Error("--timeout-ms must be a positive number.");
  }

  if (!Number.isFinite(options.waitMs) || options.waitMs < 0) {
    throw new Error("--wait-ms must be a non-negative number.");
  }

  return options;
}

function printHelp() {
  console.log(`Usage:
  node inspect_embedded_board.js --doc-url <url>

Options:
  --doc-url <url>           Match an existing doc tab by URL substring
  --timeout-ms <n>          Wait timeout for board/UI checks
  --wait-ms <n>             Extra settle time after entering the board
  --board-selector <css>    Override board container selector
`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readText(filePath) {
  return (await fsp.readFile(filePath, "utf8")).trim();
}

async function fetchJson(url, init = {}) {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

function uniquePush(list, value) {
  if (!value || list.includes(value)) {
    return;
  }
  list.push(value);
}

function extractBlockToken(url) {
  try {
    const parsed = new URL(url);
    return parsed.searchParams.get("blockToken") || null;
  } catch {
    return null;
  }
}

function chooseTargetPage(pageCandidates, docUrl) {
  if (docUrl) {
    const exact = pageCandidates.find((page) => page.url.includes(docUrl) || docUrl.includes(page.url));
    if (exact) {
      return exact;
    }
  }
  return pageCandidates.find((page) => page.url.includes("larksuite.com")) || pageCandidates[0] || null;
}

class CdpClient {
  constructor(wsUrl) {
    if (typeof WebSocket !== "function") {
      throw new Error("Global WebSocket is not available in this Node runtime.");
    }
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.requestMap = new Map();
    this.blockTokens = [];
    this.blockBodies = [];
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);

    await new Promise((resolve, reject) => {
      const cleanup = () => {
        this.ws.removeEventListener("open", onOpen);
        this.ws.removeEventListener("error", onError);
      };
      const onOpen = () => {
        cleanup();
        resolve();
      };
      const onError = (event) => {
        cleanup();
        reject(event.error || new Error("WebSocket open failed"));
      };
      this.ws.addEventListener("open", onOpen);
      this.ws.addEventListener("error", onError);
    });

    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (typeof message.id === "number") {
        const pending = this.pending.get(message.id);
        if (!pending) {
          return;
        }
        this.pending.delete(message.id);
        if (message.error) {
          pending.reject(new Error(message.error.message || JSON.stringify(message.error)));
        } else {
          pending.resolve(message.result);
        }
        return;
      }

      if (message.method === "Network.requestWillBeSent") {
        const requestId = message.params?.requestId;
        const url = message.params?.request?.url;
        if (requestId && url) {
          this.requestMap.set(requestId, { url });
          uniquePush(this.blockTokens, extractBlockToken(url));
        }
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  async getResponseBody(requestId) {
    const result = await this.send("Network.getResponseBody", { requestId });
    if (result.base64Encoded) {
      return Buffer.from(result.body, "base64").toString("utf8");
    }
    return result.body;
  }

  async harvestBlockBodies() {
    for (const [requestId, info] of this.requestMap.entries()) {
      const url = info.url || "";
      if (!url.includes("/space/api/whiteboard/block?")) {
        continue;
      }
      try {
        const body = await this.getResponseBody(requestId);
        this.blockBodies.push({ url, body });
      } catch {
        // Ignore missed bodies.
      }
    }
  }

  async close() {
    if (!this.ws) {
      return;
    }
    if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
      this.ws.close();
      await sleep(100);
    }
  }
}

async function getRootNodeId(client) {
  const { root } = await client.send("DOM.getDocument", { depth: -1, pierce: true });
  return root.nodeId;
}

async function querySelector(client, selector) {
  const rootNodeId = await getRootNodeId(client);
  const { nodeId } = await client.send("DOM.querySelector", { nodeId: rootNodeId, selector });
  return nodeId || 0;
}

async function resolveCenterPoint(client, nodeId) {
  const resolved = await client.send("DOM.resolveNode", { nodeId });
  const callResult = await client.send("Runtime.callFunctionOn", {
    objectId: resolved.object.objectId,
    functionDeclaration: `function() {
      this.scrollIntoView({ behavior: "auto", block: "center", inline: "center" });
      const rect = this.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    }`,
    returnByValue: true,
  });
  return callResult.result.value;
}

async function clickPoint(client, x, y, clickCount) {
  await client.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y, button: "none" });
  await client.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount });
  await client.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount });
}

async function waitForSelector(client, selector, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const nodeId = await querySelector(client, selector);
    if (nodeId) {
      return nodeId;
    }
    await sleep(300);
  }
  throw new Error(`Timed out waiting for selector: ${selector}`);
}

function summarizeBlockBodies(items) {
  const previewUrls = [];
  const imageTokens = [];
  const textSnippets = [];

  for (const item of items) {
    const urls = item.body.match(/https:\/\/internal-api-drive-stream-sg\.larksuite\.com\/space\/api\/box\/stream\/download\/preview\/[A-Za-z0-9]+\?preview_type=16/g) || [];
    for (const previewUrl of urls) {
      uniquePush(previewUrls, previewUrl);
      const tokenMatch = previewUrl.match(/preview\/([A-Za-z0-9]+)\?preview_type=16/);
      uniquePush(imageTokens, tokenMatch?.[1] || null);
    }

    const printable = [...new Set(item.body.match(/[\u4e00-\u9fa5A-Za-z0-9: /&().,'-]{8,}/g) || [])];
    for (const snippet of printable) {
      if (snippet.startsWith("https://")) {
        continue;
      }
      if (snippet.includes("internal-api-drive-stream")) {
        continue;
      }
      if (snippet.length > 160) {
        uniquePush(textSnippets, `${snippet.slice(0, 157)}...`);
      } else {
        uniquePush(textSnippets, snippet);
      }
    }
  }

  return { previewUrls, imageTokens, textSnippets };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const cdpPortPath = path.join(os.homedir(), ".bb-browser", "browser", "cdp-port");
  if (!fs.existsSync(cdpPortPath)) {
    throw new Error(`CDP port file not found: ${cdpPortPath}`);
  }

  const cdpPort = await readText(cdpPortPath);
  const pages = await fetchJson(`http://127.0.0.1:${cdpPort}/json/list`);
  const pageCandidates = pages.filter((page) => page.type === "page");
  const targetPage = chooseTargetPage(pageCandidates, options.docUrl);
  if (!targetPage) {
    throw new Error("Could not find a target Lark doc tab.");
  }

  const client = new CdpClient(targetPage.webSocketDebuggerUrl);
  try {
    await client.connect();
    await client.send("Page.bringToFront");
    await client.send("DOM.enable");
    await client.send("Runtime.enable");
    await client.send("Network.enable");
    await client.send("Page.reload", { ignoreCache: true });
    await sleep(1500);

    const boardNodeId = await waitForSelector(client, options.boardSelector, options.timeoutMs);
    const center = await resolveCenterPoint(client, boardNodeId);
    await clickPoint(client, center.x, center.y, 1);
    await sleep(600);
    await clickPoint(client, center.x, center.y, 2);
    await sleep(options.waitMs);
    await client.harvestBlockBodies();

    const summary = summarizeBlockBodies(client.blockBodies);
    console.log(JSON.stringify({
      ok: true,
      targetUrl: targetPage.url,
      boardSelector: options.boardSelector,
      boardBlockTokens: client.blockTokens,
      imageTokens: summary.imageTokens,
      previewUrls: summary.previewUrls,
      textSnippets: summary.textSnippets,
    }, null, 2));
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
