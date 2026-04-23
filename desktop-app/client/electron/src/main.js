const { app, BrowserWindow, dialog, ipcMain, safeStorage, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const DEFAULT_API_PORT = Number(process.env.ECOMMERCE_WORKBENCH_API_PORT || 8765);

let mainWindow = null;
let backendProcess = null;

function secretStorePath() {
  return path.join(app.getPath("userData"), "secrets.json");
}

function readSecretStore() {
  const storePath = secretStorePath();
  if (!fs.existsSync(storePath)) {
    return {};
  }

  const content = fs.readFileSync(storePath, "utf8");
  return JSON.parse(content);
}

function writeSecretStore(store) {
  fs.writeFileSync(secretStorePath(), JSON.stringify(store, null, 2), "utf8");
}

function encryptSecret(secret) {
  if (safeStorage.isEncryptionAvailable()) {
    return safeStorage.encryptString(secret).toString("base64");
  }
  return Buffer.from(secret, "utf8").toString("base64");
}

function decryptSecret(value) {
  if (!value) {
    return "";
  }
  const raw = Buffer.from(value, "base64");
  if (safeStorage.isEncryptionAvailable()) {
    return safeStorage.decryptString(raw);
  }
  return raw.toString("utf8");
}

function guessMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return (
    {
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".webp": "image/webp",
      ".txt": "text/plain",
      ".json": "application/json",
    }[ext] || "application/octet-stream"
  );
}

const runtimeState = {
  status: "booting",
  message: "Desktop shell is starting.",
  lastError: null,
  backendUrl: `http://127.0.0.1:${DEFAULT_API_PORT}`,
  paths: null,
  pythonCommand: null,
  logFile: null
};

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function resolveAppPaths() {
  const root = app.getPath("userData");
  const logs = path.join(root, "logs");
  const cache = path.join(root, "cache");
  const files = path.join(root, "files");
  const projects = path.join(files, "projects");
  const temp = path.join(files, "temp");

  [root, logs, cache, files, projects, temp].forEach(ensureDir);

  return {
    root,
    logs,
    cache,
    files,
    projects,
    temp,
    db: path.join(root, "app.db")
  };
}

function projectRoot() {
  return path.resolve(__dirname, "../../..");
}

function resolvePythonExecutable() {
  if (app.isPackaged) {
    const packagedCandidates = [
      path.join(process.resourcesPath, "python-runtime", "bin", "python3.12"),
      path.join(process.resourcesPath, "python-runtime", "bin", "python"),
    ];
    for (const candidate of packagedCandidates) {
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
  }

  const candidates = [
    process.env.ECOMMERCE_WORKBENCH_PYTHON_EXECUTABLE,
    path.join(projectRoot(), ".venv", "bin", "python"),
    path.resolve(projectRoot(), "../.venv/bin/python"),
    "python3"
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate === "python3") {
      return candidate;
    }
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return "python3";
}

function resolvePythonEntry() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "python-bundle", "main.py");
  }

  return path.join(projectRoot(), "python", "main.py");
}

function appendLogLine(logFile, line) {
  if (!logFile) {
    return;
  }
  fs.appendFileSync(logFile, `${line}\n`, "utf8");
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHealth(url, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  const healthUrl = `${url}/api/v1/system/health`;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(healthUrl);
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      // Keep retrying until timeout.
    }
    await sleep(500);
  }

  throw new Error(`Timed out waiting for backend health at ${healthUrl}`);
}

async function startBackend() {
  if (backendProcess) {
    return;
  }

  runtimeState.status = "starting_backend";
  runtimeState.message = "Starting local FastAPI service.";
  runtimeState.lastError = null;
  runtimeState.paths = resolveAppPaths();
  runtimeState.logFile = path.join(runtimeState.paths.logs, "python-api.log");
  runtimeState.pythonCommand = resolvePythonExecutable();

  const pythonEntry = resolvePythonEntry();
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    ECOMMERCE_WORKBENCH_APP_ENV: "desktop",
    ECOMMERCE_WORKBENCH_PACKAGED: app.isPackaged ? "1" : "0",
    ECOMMERCE_WORKBENCH_RESOURCE_ROOT: app.isPackaged ? process.resourcesPath : "",
    ECOMMERCE_WORKBENCH_API_HOST: "127.0.0.1",
    ECOMMERCE_WORKBENCH_API_PORT: String(DEFAULT_API_PORT),
    ECOMMERCE_WORKBENCH_APP_DATA_DIR: runtimeState.paths.root,
    ECOMMERCE_WORKBENCH_LOG_DIR: runtimeState.paths.logs,
    ECOMMERCE_WORKBENCH_CACHE_DIR: runtimeState.paths.cache,
    ECOMMERCE_WORKBENCH_FILES_DIR: runtimeState.paths.files,
    ECOMMERCE_WORKBENCH_DB_PATH: runtimeState.paths.db
  };

  appendLogLine(runtimeState.logFile, `[desktop] boot ${new Date().toISOString()}`);
  appendLogLine(
    runtimeState.logFile,
    `[desktop] spawning ${runtimeState.pythonCommand} ${pythonEntry}`
  );

  backendProcess = spawn(runtimeState.pythonCommand, [pythonEntry], {
    cwd: path.dirname(pythonEntry),
    env,
    stdio: ["ignore", "pipe", "pipe"]
  });

  backendProcess.stdout.on("data", (chunk) => {
    appendLogLine(runtimeState.logFile, chunk.toString().trimEnd());
  });

  backendProcess.stderr.on("data", (chunk) => {
    appendLogLine(runtimeState.logFile, chunk.toString().trimEnd());
  });

  backendProcess.on("exit", (code, signal) => {
    appendLogLine(
      runtimeState.logFile,
      `[desktop] backend exited code=${code ?? "null"} signal=${signal ?? "null"}`
    );
    backendProcess = null;
    if (!app.isQuitting) {
      runtimeState.status = "error";
      runtimeState.message = "Local FastAPI service stopped unexpectedly.";
      runtimeState.lastError = `Backend exited with code ${code ?? "null"}.`;
    }
  });

  try {
    const health = await waitForHealth(runtimeState.backendUrl);
    runtimeState.status = "ready";
    runtimeState.message = "Desktop shell and local FastAPI service are ready.";
    runtimeState.lastError = null;
    runtimeState.health = health;
  } catch (error) {
    runtimeState.status = "error";
    runtimeState.message = "Failed to start the local FastAPI service.";
    runtimeState.lastError = error instanceof Error ? error.message : String(error);
    appendLogLine(runtimeState.logFile, `[desktop] health check failed ${runtimeState.lastError}`);
  }
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }

  backendProcess.kill("SIGTERM");
  backendProcess = null;
}

function getRendererEntry() {
  const devUrl = process.env.ELECTRON_RENDERER_URL;
  if (devUrl) {
    return { type: "url", value: devUrl };
  }

  if (app.isPackaged) {
    return {
      type: "file",
      value: path.join(process.resourcesPath, "renderer", "index.html")
    };
  }

  return {
    type: "file",
    value: path.resolve(projectRoot(), "client/renderer/dist/index.html")
  };
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1100,
    minHeight: 720,
    backgroundColor: "#0d1117",
    title: "Ecommerce Workbench Desktop",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    }
  });

  const entry = getRendererEntry();
  if (entry.type === "url") {
    mainWindow.loadURL(entry.value);
  } else {
    mainWindow.loadFile(entry.value);
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

ipcMain.handle("runtime:get-status", async () => {
  return {
    ...runtimeState,
    backendRunning: Boolean(backendProcess)
  };
});

ipcMain.handle("app:get-info", async () => {
  return {
    name: app.getName(),
    version: app.getVersion(),
    isPackaged: app.isPackaged
  };
});

ipcMain.handle("shell:open-path", async (_event, targetPath) => {
  if (!targetPath) {
    return { ok: false, error: "Path is required." };
  }

  const result = await shell.openPath(targetPath);
  return {
    ok: !result,
    error: result || null
  };
});

ipcMain.handle("dialog:select-files", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile", "multiSelections"],
  });

  return {
    canceled: result.canceled,
    filePaths: result.filePaths,
  };
});

ipcMain.handle("dialog:select-directory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory", "createDirectory"],
  });

  return {
    canceled: result.canceled,
    filePath: result.filePaths[0] || null,
  };
});

ipcMain.handle("secret:save", async (_event, key, value) => {
  if (!key) {
    return { ok: false, error: "Secret key is required." };
  }

  const store = readSecretStore();
  store[key] = encryptSecret(value || "");
  writeSecretStore(store);
  return { ok: true };
});

ipcMain.handle("secret:read", async (_event, key) => {
  if (!key) {
    return { ok: false, error: "Secret key is required.", value: null };
  }

  const store = readSecretStore();
  if (!store[key]) {
    return { ok: true, value: null };
  }

  return {
    ok: true,
    value: decryptSecret(store[key]),
  };
});

ipcMain.handle("secret:delete", async (_event, key) => {
  if (!key) {
    return { ok: false, error: "Secret key is required." };
  }

  const store = readSecretStore();
  delete store[key];
  writeSecretStore(store);
  return { ok: true };
});

ipcMain.handle("file:read-text", async (_event, targetPath) => {
  if (!targetPath) {
    return { ok: false, error: "Path is required.", text: null };
  }
  try {
    const text = fs.readFileSync(targetPath, "utf8");
    return { ok: true, text };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      text: null,
    };
  }
});

ipcMain.handle("file:read-data-url", async (_event, targetPath) => {
  if (!targetPath) {
    return { ok: false, error: "Path is required.", dataUrl: null };
  }
  try {
    const buffer = fs.readFileSync(targetPath);
    const mimeType = guessMimeType(targetPath);
    return {
      ok: true,
      dataUrl: `data:${mimeType};base64,${buffer.toString("base64")}`,
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      dataUrl: null,
    };
  }
});

app.on("before-quit", () => {
  app.isQuitting = true;
  stopBackend();
});

app.whenReady().then(async () => {
  createMainWindow();
  await startBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});
