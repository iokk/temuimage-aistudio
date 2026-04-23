const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  getRuntimeStatus: () => ipcRenderer.invoke("runtime:get-status"),
  getAppInfo: () => ipcRenderer.invoke("app:get-info"),
  openPath: (targetPath) => ipcRenderer.invoke("shell:open-path", targetPath),
  selectFiles: () => ipcRenderer.invoke("dialog:select-files"),
  selectDirectory: () => ipcRenderer.invoke("dialog:select-directory"),
  saveSecret: (key, value) => ipcRenderer.invoke("secret:save", key, value),
  readSecret: (key) => ipcRenderer.invoke("secret:read", key),
  deleteSecret: (key) => ipcRenderer.invoke("secret:delete", key),
  readTextFile: (targetPath) => ipcRenderer.invoke("file:read-text", targetPath),
  readFileDataUrl: (targetPath) => ipcRenderer.invoke("file:read-data-url", targetPath)
});
