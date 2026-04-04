#!/usr/bin/env node

const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

function parseArgs(argv) {
  const options = {
    files: [],
    timeoutMs: 20000,
    waitMs: 8000,
    boardSelector: ".whiteboard-view-container",
    uploadSelector: ".ud__upload input[type=file]",
    preflightOnly: false,
    docUrl: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--file":
        options.files.push(argv[++i]);
        break;
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
      case "--upload-selector":
        options.uploadSelector = argv[++i];
        break;
      case "--preflight-only":
        options.preflightOnly = true;
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

  if (!options.preflightOnly && options.files.length === 0) {
    throw new Error("At least one --file is required unless --preflight-only is used.");
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
  node upload_embedded_board_images.js --doc-url <url> --file <path> [--file <path> ...]
  node upload_embedded_board_images.js --doc-url <url> --preflight-only

Options:
  --doc-url <url>           Match an existing doc tab by URL substring
  --file <path>             Local image file to upload, repeatable
  --preflight-only          Only verify board entry and upload input discovery
  --timeout-ms <n>          Wait timeout for board/UI/upload checks
  --wait-ms <n>             Extra settle time after setting file input
  --board-selector <css>    Override board container selector
  --upload-selector <css>   Override upload input selector
`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readText(filePath) {
  return (await fsp.readFile(filePath, "utf8")).trim();
}

function normalizeLocalFile(filePath) {
  const absolute = path.resolve(filePath);
  if (!fs.existsSync(absolute)) {
    throw new Error(`File does not exist: ${absolute}`);
  }
  return absolute.replace(/\\/g, "/");
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

function extractAsciiTokens(text) {
  return [...new Set(text.match(/[A-Za-z0-9]{20,}/g) || [])];
}

function summarizeEvents(events) {
  const interesting = events.filter((event) => {
    return (
      event.url.includes("/space/api/box/upload/") ||
      event.url.includes("/space/api/box/file/info/") ||
      event.url.includes("/space/api/whiteboard/list_resource") ||
      event.url.includes("/space/api/whiteboard/block?") ||
      event.url.includes("/space/api/whiteboard/room/")
    );
  });

  const unique = [];
  const seen = new Set();
  for (const event of interesting) {
    const key = `${event.method} ${event.status} ${event.url}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(event);
  }
  return unique;
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
    this.events = [];
    this.blockTokens = [];
    this.uploadFinishBodies = [];
    this.listResourceBodies = [];
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
          this.requestMap.set(requestId, {
            url,
            method: message.params.request.method,
          });
          uniquePush(this.blockTokens, extractBlockToken(url));
        }
      }

      if (message.method === "Network.responseReceived") {
        const requestId = message.params?.requestId;
        const requestInfo = requestId ? this.requestMap.get(requestId) : null;
        const url = requestInfo?.url || message.params?.response?.url;
        if (!url) {
          return;
        }

        this.events.push({
          url,
          method: requestInfo?.method || "UNKNOWN",
          status: message.params?.response?.status || null,
        });
        uniquePush(this.blockTokens, extractBlockToken(url));
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

  async harvestInterestingBodies() {
    for (const [requestId, info] of this.requestMap.entries()) {
      const url = info.url || "";
      try {
        if (url.includes("/space/api/box/upload/finish/")) {
          const body = await this.getResponseBody(requestId);
          this.uploadFinishBodies.push({ url, body });
        } else if (url.includes("/space/api/whiteboard/list_resource")) {
          const body = await this.getResponseBody(requestId);
          this.listResourceBodies.push({ url, body });
        } else if (url.includes("/space/api/whiteboard/block?")) {
          const body = await this.getResponseBody(requestId);
          this.blockBodies.push({ url, body });
        }
      } catch {
        // Some responses are not retrievable later; ignore those misses.
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
      if (!(this instanceof Element)) {
        throw new Error("Node is not an Element");
      }
      this.scrollIntoView({ behavior: "auto", block: "center", inline: "center" });
      const rect = this.getBoundingClientRect();
      if (!rect || rect.width <= 0 || rect.height <= 0) {
        throw new Error("Element is not visible");
      }
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      };
    }`,
    returnByValue: true,
  });
  return callResult.result.value;
}

async function clickPoint(client, x, y, clickCount) {
  await client.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y, button: "none" });
  await client.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x,
    y,
    button: "left",
    clickCount,
  });
  await client.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x,
    y,
    button: "left",
    clickCount,
  });
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

async function waitForAnySelector(client, selectors, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    for (const selector of selectors) {
      const nodeId = await querySelector(client, selector);
      if (nodeId) {
        return { nodeId, selector };
      }
    }
    await sleep(300);
  }
  throw new Error(`Timed out waiting for selectors: ${selectors.join(", ")}`);
}

async function clickSelector(client, selector, timeoutMs) {
  const nodeId = await waitForSelector(client, selector, timeoutMs);
  const center = await resolveCenterPoint(client, nodeId);
  await clickPoint(client, center.x, center.y, 1);
  return nodeId;
}

async function locateUploadInput(client, options) {
  const directSelectors = [options.uploadSelector].filter(Boolean);
  try {
    return await waitForAnySelector(client, directSelectors, Math.max(1500, Math.min(options.timeoutMs, 3000)));
  } catch {
    // Fall through to whiteboard toolbar fallback.
  }

  await clickSelector(client, "#whiteboard-toolbar-more", options.timeoutMs);
  await sleep(400);

  const whiteboardUploadSelectors = [
    "#whiteboard-toolbar-image-sub input[type=file]",
    "#whiteboard-toolbar-image input[type=file]",
    ".whiteboard-protal-container .ud__upload input[type=file]",
    ".whiteboard-toolbar-more-tools-e2e .ud__upload input[type=file]",
    "section[role='dialog'] .ud__upload input[type=file]",
  ];
  return waitForAnySelector(client, whiteboardUploadSelectors, options.timeoutMs);
}

async function getCdpPort() {
  const cdpPortPath = path.join(os.homedir(), ".bb-browser", "browser", "cdp-port");
  if (!fs.existsSync(cdpPortPath)) {
    throw new Error(`CDP port file not found: ${cdpPortPath}`);
  }
  return readText(cdpPortPath);
}

function chooseTargetPage(pageCandidates, docUrl) {
  if (docUrl) {
    const exact = pageCandidates.find((page) => page.url.includes(docUrl) || docUrl.includes(page.url));
    if (exact) {
      return exact;
    }
  }

  const larkPages = pageCandidates.filter((page) => page.url.includes("larksuite.com"));
  if (docUrl && larkPages.length > 0) {
    const loose = larkPages.find((page) => {
      try {
        const pageUrl = new URL(page.url);
        const targetUrl = new URL(docUrl);
        return pageUrl.hostname === targetUrl.hostname;
      } catch {
        return false;
      }
    });
    if (loose) {
      return loose;
    }
  }

  return larkPages[0] || pageCandidates[0] || null;
}

function parseUploadFinishBodies(items) {
  const fileTokens = [];
  for (const item of items) {
    try {
      const parsed = JSON.parse(item.body);
      uniquePush(fileTokens, parsed?.data?.file_token || null);
    } catch {
      // Ignore non-JSON bodies.
    }
  }
  return fileTokens;
}

function parseListResourceBodies(items) {
  const resourceTokens = [];
  for (const item of items) {
    for (const token of extractAsciiTokens(item.body)) {
      if (token.startsWith("eyJ")) {
        continue;
      }
      uniquePush(resourceTokens, token);
    }
  }
  return resourceTokens;
}

function parseBlockBodies(items) {
  const previewUrls = [];
  const imageTokens = [];
  for (const item of items) {
    const urlMatches = item.body.match(/https:\/\/internal-api-drive-stream-sg\.larksuite\.com\/space\/api\/box\/stream\/download\/preview\/[A-Za-z0-9]+\?preview_type=16/g) || [];
    for (const previewUrl of urlMatches) {
      uniquePush(previewUrls, previewUrl);
      const tokenMatch = previewUrl.match(/preview\/([A-Za-z0-9]+)\?preview_type=16/);
      uniquePush(imageTokens, tokenMatch?.[1] || null);
    }
  }
  return { previewUrls, imageTokens };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const cdpPort = await getCdpPort();
  const pages = await fetchJson(`http://127.0.0.1:${cdpPort}/json/list`);
  const pageCandidates = pages.filter((page) => page.type === "page");

  const targetPage = chooseTargetPage(pageCandidates, options.docUrl);
  if (!targetPage) {
    throw new Error("Could not find a target Lark doc tab. Open the doc first or pass --doc-url.");
  }

  const files = options.files.map(normalizeLocalFile);
  const client = new CdpClient(targetPage.webSocketDebuggerUrl);

  try {
    await client.connect();
    await client.send("Page.bringToFront");
    await client.send("DOM.enable");
    await client.send("Runtime.enable");
    await client.send("Network.enable");

    const boardNodeId = await waitForSelector(client, options.boardSelector, options.timeoutMs);
    const center = await resolveCenterPoint(client, boardNodeId);
    await clickPoint(client, center.x, center.y, 1);
    await sleep(600);
    await clickPoint(client, center.x, center.y, 2);
    await sleep(1200);

    const uploadInput = await locateUploadInput(client, options);
    const uploadInputNodeId = uploadInput.nodeId;

    if (options.preflightOnly) {
      await client.harvestInterestingBodies();
      const blockData = parseBlockBodies(client.blockBodies);
      console.log(JSON.stringify({
        ok: true,
        mode: "preflight",
        targetUrl: targetPage.url,
        boardSelector: options.boardSelector,
        uploadSelector: uploadInput.selector,
        uploadInputFound: true,
        boardBlockTokens: client.blockTokens,
        previewImageTokens: blockData.imageTokens,
      }, null, 2));
      return;
    }

    await client.send("DOM.setFileInputFiles", {
      nodeId: uploadInputNodeId,
      files,
    });

    await sleep(options.waitMs);
    await client.harvestInterestingBodies();

    const uploadFileTokens = parseUploadFinishBodies(client.uploadFinishBodies);
    const listResourceTokens = parseListResourceBodies(client.listResourceBodies);
    const blockData = parseBlockBodies(client.blockBodies);

    console.log(JSON.stringify({
      ok: true,
      mode: "upload",
      targetUrl: targetPage.url,
      files,
      uploadSelector: uploadInput.selector,
      boardBlockTokens: client.blockTokens,
      uploadFileTokens,
      listResourceTokens,
      previewImageTokens: blockData.imageTokens,
      previewUrls: blockData.previewUrls,
      requests: summarizeEvents(client.events),
    }, null, 2));
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
