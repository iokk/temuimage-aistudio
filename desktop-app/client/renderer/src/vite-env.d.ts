/// <reference types="vite/client" />

interface DesktopRuntimeStatus {
  status: string;
  message: string;
  lastError: string | null;
  backendUrl: string;
  backendRunning: boolean;
  paths: {
    root: string;
    logs: string;
    cache: string;
    files: string;
    projects: string;
    temp: string;
    db: string;
  } | null;
  pythonCommand: string | null;
  logFile: string | null;
  health?: Record<string, unknown>;
}

interface DesktopAppInfo {
  name: string;
  version: string;
  isPackaged: boolean;
}

interface DesktopBridge {
  getRuntimeStatus(): Promise<DesktopRuntimeStatus>;
  getAppInfo(): Promise<DesktopAppInfo>;
  openPath(targetPath: string): Promise<{ ok: boolean; error: string | null }>;
  selectFiles(): Promise<{ canceled: boolean; filePaths: string[] }>;
  selectDirectory(): Promise<{ canceled: boolean; filePath: string | null }>;
  saveSecret(key: string, value: string): Promise<{ ok: boolean; error?: string | null }>;
  readSecret(
    key: string
  ): Promise<{ ok: boolean; error?: string | null; value?: string | null }>;
  deleteSecret(key: string): Promise<{ ok: boolean; error?: string | null }>;
  readTextFile(
    targetPath: string
  ): Promise<{ ok: boolean; error?: string | null; text?: string | null }>;
  readFileDataUrl(
    targetPath: string
  ): Promise<{ ok: boolean; error?: string | null; dataUrl?: string | null }>;
}

declare global {
  interface Window {
    desktop: DesktopBridge;
  }
}

export {};
