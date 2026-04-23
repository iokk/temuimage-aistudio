import { FormEvent, useEffect, useMemo, useState } from "react";

interface RuntimeStatus {
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

interface AppInfo {
  name: string;
  version: string;
  isPackaged: boolean;
}

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  base_url: string;
  title_model: string;
  vision_model: string;
  image_model: string;
  enabled: boolean;
  is_default: boolean;
  secret_ref: string;
  created_at: string;
  updated_at: string;
}

interface Task {
  id: string;
  task_type: string;
  status: string;
  project_id: string;
  provider_id: string;
  payload: Record<string, unknown>;
  progress_total: number;
  progress_done: number;
  current_step: string;
  error_message: string;
  created_at: string;
  started_at: string;
  ended_at: string;
  updated_at: string;
}

interface TaskEvent {
  id: string;
  task_id: string;
  level: string;
  event_type: string;
  message: string;
  detail: Record<string, unknown>;
  created_at: string;
}

interface Project {
  id: string;
  project_type: string;
  summary: string;
  status: string;
  record_state: string;
  provider_id: string;
  title_language: string;
  image_language: string;
  artifact_dir: string;
  zip_path: string;
  cover_file_id: string;
  created_at: string;
  started_at: string;
  completed_at: string;
  updated_at: string;
  trashed_at: string;
  purged_at: string;
  files: Array<{
    id: string;
    file_role: string;
    file_name: string;
    file_path: string;
    mime_type: string;
    file_size: number;
    created_at: string;
  }>;
  title_text: string;
}

interface Setting {
  key: string;
  value: unknown;
  updated_at: string;
}

interface DiagnosticsSummary {
  providers_total: number;
  providers_enabled: number;
  tasks_total: number;
  tasks_running: number;
  tasks_failed: number;
  projects_total: number;
  projects_failed: number;
  projects_succeeded: number;
  files_total: number;
  files_size_bytes: number;
}

type HealthPayload = Record<string, unknown> | null;

type ProviderFormState = {
  name: string;
  apiKey: string;
  titleModel: string;
  visionModel: string;
  imageModel: string;
  baseUrl: string;
};

type TitleFormState = {
  providerId: string;
  titleLanguage: string;
  productInfo: string;
  templatePrompt: string;
  inputMode: "text" | "image" | "hybrid";
};

type TranslationFormState = {
  providerId: string;
  imageLanguage: string;
  complianceMode: "strict" | "balanced";
  aspectRatio: string;
  imageModel: string;
};

type QuickGenerateFormState = {
  providerId: string;
  productName: string;
  productDetail: string;
  outputLanguage: string;
  aspectRatio: string;
  imageModel: string;
  quickMode: "hero" | "feature" | "lifestyle";
  imageCount: number;
};

type SmartGenerateFormState = {
  providerId: string;
  productName: string;
  productDetail: string;
  imageLanguage: string;
  aspectRatio: string;
  imageModel: string;
};

const DEFAULT_PROVIDER_FORM: ProviderFormState = {
  name: "",
  apiKey: "",
  titleModel: "gemini-3.1-flash-lite-preview",
  visionModel: "gemini-3.1-flash-lite-preview",
  imageModel: "nano-banana",
  baseUrl: "",
};

const DEFAULT_TITLE_FORM: TitleFormState = {
  providerId: "",
  titleLanguage: "en",
  productInfo: "",
  templatePrompt:
    "You are writing ecommerce product titles. Product details: {product_info}. Generate three strong title strategies: search optimization, conversion optimization, and differentiation. English title length must stay within the required range.",
  inputMode: "text",
};

const DEFAULT_TRANSLATION_FORM: TranslationFormState = {
  providerId: "",
  imageLanguage: "en",
  complianceMode: "strict",
  aspectRatio: "1:1",
  imageModel: "nano-banana",
};

const DEFAULT_QUICK_FORM: QuickGenerateFormState = {
  providerId: "",
  productName: "",
  productDetail: "",
  outputLanguage: "en",
  aspectRatio: "1:1",
  imageModel: "nano-banana",
  quickMode: "hero",
  imageCount: 1,
};

const DEFAULT_SMART_FORM: SmartGenerateFormState = {
  providerId: "",
  productName: "",
  productDetail: "",
  imageLanguage: "en",
  aspectRatio: "1:1",
  imageModel: "nano-banana",
};

const SMART_TYPE_OPTIONS = [
  { key: "S1", label: "卖点图" },
  { key: "S2", label: "场景图" },
  { key: "S3", label: "细节图" },
  { key: "S4", label: "对比图" },
  { key: "S5", label: "规格图" },
];

function StatusBadge({ status }: { status: string }) {
  const label = {
    booting: "Booting",
    starting_backend: "Starting backend",
    ready: "Ready",
    error: "Error",
    queued: "Queued",
    running: "Running",
    succeeded: "Succeeded",
    failed: "Failed"
  }[status] || status;

  return <span className={`status-badge status-${status}`}>{label}</span>;
}

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="section-header">
      <span className="section-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      <p>{description}</p>
    </header>
  );
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export default function App() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [health, setHealth] = useState<HealthPayload>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsSummary | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectDetail, setProjectDetail] = useState<Project | null>(null);
  const [taskEvents, setTaskEvents] = useState<TaskEvent[]>([]);
  const [projectPreviewText, setProjectPreviewText] = useState<string>("");
  const [projectPreviewImage, setProjectPreviewImage] = useState<string>("");
  const [providerForm, setProviderForm] = useState<ProviderFormState>(DEFAULT_PROVIDER_FORM);
  const [titleForm, setTitleForm] = useState<TitleFormState>(DEFAULT_TITLE_FORM);
  const [translationForm, setTranslationForm] =
    useState<TranslationFormState>(DEFAULT_TRANSLATION_FORM);
  const [quickForm, setQuickForm] = useState<QuickGenerateFormState>(DEFAULT_QUICK_FORM);
  const [smartForm, setSmartForm] = useState<SmartGenerateFormState>(DEFAULT_SMART_FORM);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [translationError, setTranslationError] = useState<string | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);
  const [smartError, setSmartError] = useState<string | null>(null);
  const [selectedDirectory, setSelectedDirectory] = useState<string>("");
  const [selectedTitleFiles, setSelectedTitleFiles] = useState<string[]>([]);
  const [selectedTranslateFiles, setSelectedTranslateFiles] = useState<string[]>([]);
  const [selectedQuickFiles, setSelectedQuickFiles] = useState<string[]>([]);
  const [selectedSmartFiles, setSelectedSmartFiles] = useState<string[]>([]);
  const [smartTypeCounts, setSmartTypeCounts] = useState<Record<string, number>>({
    S1: 1,
    S2: 1,
  });
  const [submittingProvider, setSubmittingProvider] = useState(false);
  const [submittingTitle, setSubmittingTitle] = useState(false);
  const [submittingTranslation, setSubmittingTranslation] = useState(false);
  const [submittingQuick, setSubmittingQuick] = useState(false);
  const [submittingSmart, setSubmittingSmart] = useState(false);
  const [settingsSaveMessage, setSettingsSaveMessage] = useState<string>("");
  const [providerTestMessages, setProviderTestMessages] = useState<Record<string, string>>({});
  const [settingsDrafts, setSettingsDrafts] = useState<{
    defaultModel: string;
    defaultTitleModel: string;
    defaultVisionModel: string;
  }>({
    defaultModel: "nano-banana",
    defaultTitleModel: "gemini-3.1-flash-lite-preview",
    defaultVisionModel: "gemini-3.1-flash-lite-preview",
  });
  const [taskStatusFilter, setTaskStatusFilter] = useState<string>("all");
  const [projectStateFilter, setProjectStateFilter] = useState<string>("active");
  const [projectStatusFilter, setProjectStatusFilter] = useState<string>("all");
  const [projectSearch, setProjectSearch] = useState<string>("");

  const backendUrl = runtime?.backendUrl || "";
  const defaultSettings = useMemo(
    () => ({
      defaultTitleLanguage:
        String(settings.find((item) => item.key === "default_title_language")?.value || "en"),
      defaultImageLanguage:
        String(settings.find((item) => item.key === "default_image_language")?.value || "en"),
      defaultModel:
        String(settings.find((item) => item.key === "default_model")?.value || "nano-banana"),
      defaultTitleModel: String(
        settings.find((item) => item.key === "default_title_model")?.value ||
          "gemini-3.1-flash-lite-preview"
      ),
      defaultVisionModel: String(
        settings.find((item) => item.key === "default_vision_model")?.value ||
          "gemini-3.1-flash-lite-preview"
      ),
      defaultOutputDir: String(
        settings.find((item) => item.key === "default_output_dir")?.value || ""
      ),
    }),
    [settings]
  );
  const filteredTasks = useMemo(
    () =>
      tasks.filter((task) =>
        taskStatusFilter === "all" ? true : task.status === taskStatusFilter
      ),
    [tasks, taskStatusFilter]
  );
  const filteredProjects = useMemo(
    () =>
      projects.filter((project) => {
        const stateMatch =
          projectStateFilter === "all" ? true : project.record_state === projectStateFilter;
        const statusMatch =
          projectStatusFilter === "all" ? true : project.status === projectStatusFilter;
        const searchMatch =
          !projectSearch.trim() ||
          project.summary.toLowerCase().includes(projectSearch.trim().toLowerCase()) ||
          project.project_type.toLowerCase().includes(projectSearch.trim().toLowerCase());
        return stateMatch && statusMatch && searchMatch;
      }),
    [projects, projectStateFilter, projectStatusFilter, projectSearch]
  );
  const selectedProject =
    filteredProjects.find((project) => project.id === selectedProjectId) ||
    filteredProjects[0] ||
    null;
  const selectedTask = tasks.find((task) => task.id === selectedTaskId) || tasks[0] || null;

  useEffect(() => {
    setSettingsDrafts({
      defaultModel: defaultSettings.defaultModel,
      defaultTitleModel: defaultSettings.defaultTitleModel,
      defaultVisionModel: defaultSettings.defaultVisionModel,
    });
  }, [
    defaultSettings.defaultModel,
    defaultSettings.defaultTitleModel,
    defaultSettings.defaultVisionModel,
  ]);

  const loadDashboard = async (backendBaseUrl: string) => {
    const [nextHealth, nextProviders, nextSettings, nextDiagnostics, nextTasks, nextProjects] =
      await Promise.all([
        fetchJson<Record<string, unknown>>(`${backendBaseUrl}/api/v1/system/health`),
        fetchJson<Provider[]>(`${backendBaseUrl}/api/v1/providers`),
        fetchJson<Setting[]>(`${backendBaseUrl}/api/v1/settings`),
        fetchJson<DiagnosticsSummary>(`${backendBaseUrl}/api/v1/diagnostics/summary`),
        fetchJson<Task[]>(`${backendBaseUrl}/api/v1/tasks`),
        fetchJson<Project[]>(`${backendBaseUrl}/api/v1/projects?record_state=all`),
      ]);

    setHealth(nextHealth);
    setProviders(nextProviders);
    setSettings(nextSettings);
    setDiagnostics(nextDiagnostics);
    setTasks(nextTasks);
    setProjects(nextProjects);
    setSelectedTaskId((previous) =>
      previous && nextTasks.some((task) => task.id === previous) ? previous : nextTasks[0]?.id || ""
    );
    setSelectedProjectId((previous) =>
      previous && nextProjects.some((project) => project.id === previous)
        ? previous
        : nextProjects[0]?.id || ""
    );
    setTitleForm((previous) => ({
      ...previous,
      providerId:
        previous.providerId ||
        nextProviders.find((provider) => provider.is_default)?.id ||
        nextProviders[0]?.id ||
        "",
    }));
    setTranslationForm((previous) => ({
      ...previous,
      providerId:
        previous.providerId ||
        nextProviders.find((provider) => provider.is_default)?.id ||
        nextProviders[0]?.id ||
        "",
    }));
    setQuickForm((previous) => ({
      ...previous,
      providerId:
        previous.providerId ||
        nextProviders.find((provider) => provider.is_default)?.id ||
        nextProviders[0]?.id ||
        "",
    }));
    setSmartForm((previous) => ({
      ...previous,
      providerId:
        previous.providerId ||
        nextProviders.find((provider) => provider.is_default)?.id ||
        nextProviders[0]?.id ||
        "",
    }));
  };

  useEffect(() => {
    let mounted = true;

    const loadAppInfo = async () => {
      const info = await window.desktop.getAppInfo();
      if (mounted) {
        setAppInfo(info);
      }
    };

    const loadRuntime = async () => {
      try {
        const nextRuntime = await window.desktop.getRuntimeStatus();
        if (!mounted) {
          return;
        }
        setRuntime(nextRuntime);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setHealthError(error instanceof Error ? error.message : String(error));
      }
    };

    loadAppInfo().catch(console.error);
    loadRuntime().catch(console.error);
    const timer = window.setInterval(() => {
      loadRuntime().catch(console.error);
    }, 1000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!backendUrl || runtime?.status !== "ready") {
      return;
    }

    let mounted = true;

    const loadData = async () => {
      try {
        if (!mounted) {
          return;
        }

        await loadDashboard(backendUrl);
        setHealthError(null);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setHealthError(error instanceof Error ? error.message : String(error));
      }
    };

    loadData().catch(console.error);
    const timer = window.setInterval(() => {
      loadData().catch(console.error);
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [backendUrl, runtime?.status]);

  useEffect(() => {
    if (!backendUrl || !selectedTask) {
      setTaskEvents([]);
      return;
    }

    let mounted = true;

    const loadEvents = async () => {
      try {
        const events = await fetchJson<TaskEvent[]>(
          `${backendUrl}/api/v1/tasks/${selectedTask.id}/events`
        );
        if (mounted) {
          setTaskEvents(events);
        }
      } catch (error) {
        if (mounted) {
          setTaskEvents([]);
        }
      }
    };

    loadEvents().catch(console.error);
    const timer = window.setInterval(() => {
      loadEvents().catch(console.error);
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [backendUrl, selectedTask?.id]);

  useEffect(() => {
    if (!backendUrl || !selectedProject) {
      setProjectDetail(null);
      setProjectPreviewText("");
      setProjectPreviewImage("");
      return;
    }

    let mounted = true;

    const loadProjectDetail = async () => {
      try {
        const detail = await fetchJson<Project>(
          `${backendUrl}/api/v1/projects/${selectedProject.id}`
        );
        if (mounted) {
          setProjectDetail(detail);
        }
      } catch (error) {
        if (mounted) {
          setProjectDetail(null);
          setProjectPreviewText("");
          setProjectPreviewImage("");
        }
      }
    };

    loadProjectDetail().catch(console.error);
    const timer = window.setInterval(() => {
      loadProjectDetail().catch(console.error);
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [backendUrl, selectedProject?.id]);

  useEffect(() => {
    if (!projectDetail) {
      setProjectPreviewText("");
      setProjectPreviewImage("");
      return;
    }

    let cancelled = false;

    const loadPreview = async () => {
      const preferredImage =
        projectDetail.files.find((file) => file.file_role === "generated_output") ||
        projectDetail.files.find((file) => file.file_role === "translated_output") ||
        projectDetail.files.find((file) => file.file_role === "input_image");
      const preferredText =
        projectDetail.title_text
          ? null
          : projectDetail.files.find((file) => file.file_role === "title_output") ||
            projectDetail.files.find((file) => file.file_role === "metadata");

      if (projectDetail.title_text) {
        setProjectPreviewText(projectDetail.title_text);
      } else if (preferredText) {
        const textResult = await window.desktop.readTextFile(preferredText.file_path);
        if (!cancelled) {
          setProjectPreviewText(textResult.text || "");
        }
      } else {
        setProjectPreviewText("");
      }

      if (preferredImage) {
        const imageResult = await window.desktop.readFileDataUrl(preferredImage.file_path);
        if (!cancelled) {
          setProjectPreviewImage(imageResult.dataUrl || "");
        }
      } else {
        setProjectPreviewImage("");
      }
    };

    loadPreview().catch(() => {
      if (!cancelled) {
        setProjectPreviewText("");
        setProjectPreviewImage("");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [projectDetail]);

  const canOpenLogs = useMemo(() => Boolean(runtime?.paths?.logs), [runtime]);

  const handleSelectDirectory = async () => {
    const result = await window.desktop.selectDirectory();
    if (!result.canceled && result.filePath) {
      setSelectedDirectory(result.filePath);
      if (backendUrl) {
        await fetchJson(`${backendUrl}/api/v1/settings/default_output_dir`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            value: result.filePath,
          }),
        });
      }
    }
  };

  const handleCreateProvider = async (event: FormEvent) => {
    event.preventDefault();
    if (!backendUrl) {
      return;
    }
    setSubmittingProvider(true);
    setProviderError(null);

    try {
      const secretRef = `provider:${crypto.randomUUID()}`;
      const saveResult = await window.desktop.saveSecret(secretRef, providerForm.apiKey);
      if (!saveResult.ok) {
        throw new Error(saveResult.error || "Failed to save provider secret.");
      }

      await fetchJson<Provider>(`${backendUrl}/api/v1/providers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: providerForm.name,
          provider_type: "gemini",
          base_url: providerForm.baseUrl,
          title_model: providerForm.titleModel,
          vision_model: providerForm.visionModel,
          image_model: providerForm.imageModel,
          enabled: true,
          is_default: providers.length === 0,
          secret_ref: secretRef,
        }),
      });

      setProviderForm(DEFAULT_PROVIDER_FORM);
      await loadDashboard(backendUrl);
    } catch (error) {
      setProviderError(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmittingProvider(false);
    }
  };

  const handleSetDefaultProvider = async (provider: Provider) => {
    if (!backendUrl) {
      return;
    }
    try {
      await fetchJson<Provider>(`${backendUrl}/api/v1/providers/${provider.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: provider.name,
          provider_type: provider.provider_type,
          base_url: provider.base_url,
          title_model: provider.title_model,
          vision_model: provider.vision_model,
          image_model: provider.image_model,
          enabled: provider.enabled,
          is_default: true,
          secret_ref: provider.secret_ref,
        }),
      });
      await loadDashboard(backendUrl);
    } catch (error) {
      setProviderError(error instanceof Error ? error.message : String(error));
    }
  };

  const handleDeleteProvider = async (provider: Provider) => {
    if (!backendUrl) {
      return;
    }
    try {
      await fetchJson<{ ok: boolean }>(`${backendUrl}/api/v1/providers/${provider.id}`, {
        method: "DELETE",
      });
      await window.desktop.deleteSecret(provider.secret_ref);
      await loadDashboard(backendUrl);
    } catch (error) {
      setProviderError(error instanceof Error ? error.message : String(error));
    }
  };

  const handleToggleProvider = async (provider: Provider) => {
    if (!backendUrl) {
      return;
    }
    try {
      await fetchJson<Provider>(`${backendUrl}/api/v1/providers/${provider.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: provider.name,
          provider_type: provider.provider_type,
          base_url: provider.base_url,
          title_model: provider.title_model,
          vision_model: provider.vision_model,
          image_model: provider.image_model,
          enabled: !provider.enabled,
          is_default: provider.is_default,
          secret_ref: provider.secret_ref,
        }),
      });
      await loadDashboard(backendUrl);
    } catch (error) {
      setProviderError(error instanceof Error ? error.message : String(error));
    }
  };

  const handleTestProvider = async (provider: Provider) => {
    if (!backendUrl) {
      return;
    }
    try {
      const secretResult = await window.desktop.readSecret(provider.secret_ref);
      if (!secretResult.ok || !secretResult.value) {
        throw new Error(secretResult.error || "Provider secret is missing.");
      }
      const result = await fetchJson<{ ok: boolean; message: string }>(
        `${backendUrl}/api/v1/providers/test`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            api_key: secretResult.value,
            title_model: provider.title_model,
            base_url: provider.base_url,
          }),
        }
      );
      setProviderTestMessages((previous) => ({
        ...previous,
        [provider.id]: result.ok ? `OK: ${result.message}` : `Fail: ${result.message}`,
      }));
    } catch (error) {
      setProviderTestMessages((previous) => ({
        ...previous,
        [provider.id]: error instanceof Error ? error.message : String(error),
      }));
    }
  };

  const handleSelectTitleFiles = async () => {
    const result = await window.desktop.selectFiles();
    if (!result.canceled) {
      setSelectedTitleFiles(result.filePaths);
      setTitleForm((previous) => ({
        ...previous,
        inputMode: previous.inputMode === "text" ? "hybrid" : previous.inputMode,
      }));
    }
  };

  const handleSelectTranslateFiles = async () => {
    const result = await window.desktop.selectFiles();
    if (!result.canceled) {
      setSelectedTranslateFiles(result.filePaths);
    }
  };

  const handleSelectQuickFiles = async () => {
    const result = await window.desktop.selectFiles();
    if (!result.canceled) {
      setSelectedQuickFiles(result.filePaths);
    }
  };

  const handleSelectSmartFiles = async () => {
    const result = await window.desktop.selectFiles();
    if (!result.canceled) {
      setSelectedSmartFiles(result.filePaths);
    }
  };

  const handleSubmitTitleWorkflow = async (event: FormEvent) => {
    event.preventDefault();
    if (!backendUrl) {
      return;
    }
    setSubmittingTitle(true);
    setTitleError(null);

    try {
      const provider = providers.find((item) => item.id === titleForm.providerId);
      if (!provider) {
        throw new Error("Please select a provider before generating titles.");
      }
      if (!titleForm.productInfo.trim() && selectedTitleFiles.length === 0) {
        throw new Error("Please provide product information or choose at least one image.");
      }

      const secretResult = await window.desktop.readSecret(provider.secret_ref);
      if (!secretResult.ok || !secretResult.value) {
        throw new Error(secretResult.error || "Provider secret is missing.");
      }

      await fetchJson<{ task_id: string; project_id: string; status: string }>(
        `${backendUrl}/api/v1/workflows/title`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            provider_id: titleForm.providerId,
            api_key: secretResult.value,
            product_info: titleForm.productInfo,
            template_prompt: titleForm.templatePrompt,
            title_language: titleForm.titleLanguage,
            image_paths: selectedTitleFiles,
          }),
        }
      );

      await loadDashboard(backendUrl);
    } catch (error) {
      setTitleError(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmittingTitle(false);
    }
  };

  const handleSubmitTranslationWorkflow = async (event: FormEvent) => {
    event.preventDefault();
    if (!backendUrl) {
      return;
    }
    setSubmittingTranslation(true);
    setTranslationError(null);

    try {
      const provider = providers.find((item) => item.id === translationForm.providerId);
      if (!provider) {
        throw new Error("Please select a provider before translating images.");
      }
      if (!selectedTranslateFiles.length) {
        throw new Error("Please choose at least one image to translate.");
      }

      const secretResult = await window.desktop.readSecret(provider.secret_ref);
      if (!secretResult.ok || !secretResult.value) {
        throw new Error(secretResult.error || "Provider secret is missing.");
      }

      await fetchJson<{ task_id: string; project_id: string; status: string }>(
        `${backendUrl}/api/v1/workflows/translate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            provider_id: translationForm.providerId,
            api_key: secretResult.value,
            image_paths: selectedTranslateFiles,
            image_language: translationForm.imageLanguage,
            compliance_mode: translationForm.complianceMode,
            aspect_ratio: translationForm.aspectRatio,
            image_model: translationForm.imageModel,
          }),
        }
      );

      await loadDashboard(backendUrl);
    } catch (error) {
      setTranslationError(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmittingTranslation(false);
    }
  };

  const handleSubmitQuickWorkflow = async (event: FormEvent) => {
    event.preventDefault();
    if (!backendUrl) {
      return;
    }
    setSubmittingQuick(true);
    setQuickError(null);

    try {
      const provider = providers.find((item) => item.id === quickForm.providerId);
      if (!provider) {
        throw new Error("Please select a provider before running quick generation.");
      }
      if (!selectedQuickFiles.length) {
        throw new Error("Please choose at least one reference image.");
      }
      if (!quickForm.productName.trim()) {
        throw new Error("Please provide a product name.");
      }

      const secretResult = await window.desktop.readSecret(provider.secret_ref);
      if (!secretResult.ok || !secretResult.value) {
        throw new Error(secretResult.error || "Provider secret is missing.");
      }

      await fetchJson<{ task_id: string; project_id: string; status: string }>(
        `${backendUrl}/api/v1/workflows/quick-generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            provider_id: quickForm.providerId,
            api_key: secretResult.value,
            image_paths: selectedQuickFiles,
            product_name: quickForm.productName,
            product_detail: quickForm.productDetail,
            output_language: quickForm.outputLanguage,
            aspect_ratio: quickForm.aspectRatio,
            image_model: quickForm.imageModel,
            quick_mode: quickForm.quickMode,
            image_count: quickForm.imageCount,
          }),
        }
      );

      await loadDashboard(backendUrl);
    } catch (error) {
      setQuickError(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmittingQuick(false);
    }
  };

  const handleSubmitSmartWorkflow = async (event: FormEvent) => {
    event.preventDefault();
    if (!backendUrl) {
      return;
    }
    setSubmittingSmart(true);
    setSmartError(null);

    try {
      const provider = providers.find((item) => item.id === smartForm.providerId);
      if (!provider) {
        throw new Error("Please select a provider before running smart generation.");
      }
      if (!selectedSmartFiles.length) {
        throw new Error("Please choose at least one reference image.");
      }
      if (!smartForm.productName.trim()) {
        throw new Error("Please provide a product name.");
      }

      const selectedTypes = Object.fromEntries(
        Object.entries(smartTypeCounts).filter(([, value]) => value > 0)
      );
      if (!Object.keys(selectedTypes).length) {
        throw new Error("Please select at least one smart output type.");
      }

      const secretResult = await window.desktop.readSecret(provider.secret_ref);
      if (!secretResult.ok || !secretResult.value) {
        throw new Error(secretResult.error || "Provider secret is missing.");
      }

      await fetchJson<{ task_id: string; project_id: string; status: string }>(
        `${backendUrl}/api/v1/workflows/smart-generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            provider_id: smartForm.providerId,
            api_key: secretResult.value,
            image_paths: selectedSmartFiles,
            product_name: smartForm.productName,
            product_detail: smartForm.productDetail,
            image_language: smartForm.imageLanguage,
            aspect_ratio: smartForm.aspectRatio,
            image_model: smartForm.imageModel,
            selected_types: selectedTypes,
          }),
        }
      );

      await loadDashboard(backendUrl);
    } catch (error) {
      setSmartError(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmittingSmart(false);
    }
  };

  const handleSaveDefaultSetting = async (key: string, value: string) => {
    if (!backendUrl) {
      return;
    }
    try {
      await fetchJson(`${backendUrl}/api/v1/settings/${key}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ value }),
      });
      setSettingsSaveMessage(`Saved ${key}.`);
      await loadDashboard(backendUrl);
    } catch (error) {
      setSettingsSaveMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const handleProjectAction = async (
    projectId: string,
    action: "trash" | "restore" | "purge"
  ) => {
    if (!backendUrl) {
      return;
    }
    try {
      if (action === "purge") {
        await fetchJson<{ ok: boolean }>(`${backendUrl}/api/v1/projects/${projectId}`, {
          method: "DELETE",
        });
      } else {
        await fetchJson<Project>(`${backendUrl}/api/v1/projects/${projectId}/${action}`, {
          method: "POST",
        });
      }
      await loadDashboard(backendUrl);
    } catch (error) {
      setHealthError(error instanceof Error ? error.message : String(error));
    }
  };

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-topline">Slice 3 Title Workflow</div>
        <div className="hero-headline">
          <h1>Ecommerce Workbench Desktop</h1>
          <StatusBadge status={runtime?.status || "booting"} />
        </div>
        <p className="hero-copy">
          The desktop shell is now running a real workflow foundation: local SQLite state,
          provider storage, task polling, project records, and the first title-generation
          pipeline.
        </p>

        <div className="hero-grid">
          <article className="info-card">
            <h2>Desktop shell</h2>
            <p>{runtime?.message || "Desktop shell is starting."}</p>
            <dl>
              <div>
                <dt>App</dt>
                <dd>{appInfo ? `${appInfo.name} ${appInfo.version}` : "Loading..."}</dd>
              </div>
              <div>
                <dt>Python</dt>
                <dd>{runtime?.pythonCommand || "Resolving..."}</dd>
              </div>
              <div>
                <dt>Health</dt>
                <dd>{health ? "Connected" : "Waiting..."}</dd>
              </div>
            </dl>
          </article>

          <article className="info-card">
            <h2>System health</h2>
            <p className={runtime?.status === "ready" ? "success-copy" : "muted-copy"}>
              {runtime?.status === "ready"
                ? "FastAPI, SQLite, and desktop runtime are responding."
                : "Waiting for local FastAPI readiness."}
            </p>
            {healthError ? <p className="error-copy">{healthError}</p> : null}
            <pre>{JSON.stringify(health, null, 2)}</pre>
          </article>
        </div>

        <div className="path-grid">
          <article className="path-card">
            <h3>App data</h3>
            <p>{runtime?.paths?.root || "Preparing..."}</p>
          </article>
          <article className="path-card">
            <h3>SQLite</h3>
            <p>{runtime?.paths?.db || "Preparing..."}</p>
          </article>
          <article className="path-card">
            <h3>Output directory</h3>
            <p>{selectedDirectory || String(settings.find((item) => item.key === "default_output_dir")?.value || "Unset")}</p>
          </article>
        </div>

        <div className="hero-actions">
          <button
            type="button"
            className="action-button"
            onClick={() => runtime?.paths?.logs && window.desktop.openPath(runtime.paths.logs)}
            disabled={!canOpenLogs}
          >
            Open logs
          </button>
          <button
            type="button"
            className="action-button secondary"
            onClick={() => runtime?.paths?.root && window.desktop.openPath(runtime.paths.root)}
            disabled={!runtime?.paths?.root}
          >
            Open app data
          </button>
          <button type="button" className="action-button secondary" onClick={handleSelectDirectory}>
            Pick output directory
          </button>
        </div>

        {runtime?.lastError ? <p className="error-banner">{runtime.lastError}</p> : null}
      </section>

      <section className="workspace-grid">
        <article className="workspace-card">
          <SectionHeader
            eyebrow="Providers"
            title="Create a Gemini provider"
            description="Secrets stay in the desktop shell. SQLite only stores the secret reference."
          />

          <form className="form-grid" onSubmit={handleCreateProvider}>
            <label>
              Provider name
              <input
                value={providerForm.name}
                onChange={(event) =>
                  setProviderForm((previous) => ({ ...previous, name: event.target.value }))
                }
                placeholder="My Gemini Key"
                required
              />
            </label>
            <label>
              API key
              <input
                type="password"
                value={providerForm.apiKey}
                onChange={(event) =>
                  setProviderForm((previous) => ({ ...previous, apiKey: event.target.value }))
                }
                placeholder="AIza..."
                required
              />
            </label>
            <label>
              Title model
              <input
                value={providerForm.titleModel}
                onChange={(event) =>
                  setProviderForm((previous) => ({
                    ...previous,
                    titleModel: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Vision model
              <input
                value={providerForm.visionModel}
                onChange={(event) =>
                  setProviderForm((previous) => ({
                    ...previous,
                    visionModel: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Image model
              <input
                value={providerForm.imageModel}
                onChange={(event) =>
                  setProviderForm((previous) => ({
                    ...previous,
                    imageModel: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Base URL
              <input
                value={providerForm.baseUrl}
                onChange={(event) =>
                  setProviderForm((previous) => ({ ...previous, baseUrl: event.target.value }))
                }
                placeholder="Optional relay URL"
              />
            </label>

            {providerError ? <p className="error-copy">{providerError}</p> : null}

            <button type="submit" className="action-button" disabled={submittingProvider}>
              {submittingProvider ? "Saving provider..." : "Save provider"}
            </button>
          </form>

          <div className="collection-list">
            {providers.map((provider) => (
              <div key={provider.id} className="collection-item">
                <div className="collection-meta">
                  <strong>{provider.name}</strong>
                  <span>{provider.title_model || "No title model configured"}</span>
                </div>
                <div className="collection-side">
                  {provider.is_default ? <span className="micro-pill">Default</span> : null}
                  <span className="micro-pill subtle">{provider.provider_type}</span>
                  {!provider.is_default ? (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => handleSetDefaultProvider(provider)}
                    >
                      Set default
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => handleToggleProvider(provider)}
                  >
                    {provider.enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => handleTestProvider(provider)}
                  >
                    Test
                  </button>
                  <button
                    type="button"
                    className="text-button danger"
                    onClick={() => handleDeleteProvider(provider)}
                  >
                    Delete
                  </button>
                </div>
                {providerTestMessages[provider.id] ? (
                  <p className="provider-test-note">{providerTestMessages[provider.id]}</p>
                ) : null}
              </div>
            ))}
            {!providers.length ? (
              <p className="muted-copy">No providers yet. Save one to unlock the title workflow.</p>
            ) : null}
          </div>
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Title workflow"
            title="Run the first real task pipeline"
            description="This slice uses text-mode title generation end to end: submission, background execution, events, and project archiving."
          />

          <form className="form-grid" onSubmit={handleSubmitTitleWorkflow}>
            <label>
              Provider
              <select
                value={titleForm.providerId}
                onChange={(event) =>
                  setTitleForm((previous) => ({ ...previous, providerId: event.target.value }))
                }
                required
              >
                <option value="">Select a provider</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Input mode
              <select
                value={titleForm.inputMode}
                onChange={(event) =>
                  setTitleForm((previous) => ({
                    ...previous,
                    inputMode: event.target.value as TitleFormState["inputMode"],
                  }))
                }
              >
                <option value="text">Text only</option>
                <option value="image">Images only</option>
                <option value="hybrid">Images + text</option>
              </select>
            </label>

            <label>
              Target language
              <select
                value={titleForm.titleLanguage}
                onChange={(event) =>
                  setTitleForm((previous) => ({ ...previous, titleLanguage: event.target.value }))
                }
              >
                <option value="en">English only</option>
                <option value="zh">English + 中文</option>
                <option value="ja">English + 日本語</option>
                <option value="fr">English + Français</option>
                <option value="es">English + Español</option>
              </select>
            </label>

            <label className="span-2">
              Product information
              <textarea
                value={titleForm.productInfo}
                onChange={(event) =>
                  setTitleForm((previous) => ({ ...previous, productInfo: event.target.value }))
                }
                placeholder="Describe the product, materials, dimensions, audience, and key selling points."
                rows={7}
                required={titleForm.inputMode !== "image"}
              />
            </label>

            <div className="span-2 upload-card">
              <div className="upload-card-copy">
                <strong>Reference images</strong>
                <p>
                  Use local files for image analysis mode or hybrid mode. Paths stay local to the
                  desktop app.
                </p>
                <span className="mono">
                  {selectedTitleFiles.length
                    ? `${selectedTitleFiles.length} file(s) selected`
                    : "No images selected"}
                </span>
              </div>
              <div className="hero-actions compact-actions">
                <button
                  type="button"
                  className="action-button secondary"
                  onClick={handleSelectTitleFiles}
                >
                  Choose images
                </button>
                {selectedTitleFiles.length ? (
                  <button
                    type="button"
                    className="action-button secondary"
                    onClick={() => setSelectedTitleFiles([])}
                  >
                    Clear images
                  </button>
                ) : null}
              </div>
            </div>

            <label className="span-2">
              Template prompt
              <textarea
                value={titleForm.templatePrompt}
                onChange={(event) =>
                  setTitleForm((previous) => ({
                    ...previous,
                    templatePrompt: event.target.value,
                  }))
                }
                rows={6}
              />
            </label>

            {titleError ? <p className="error-copy span-2">{titleError}</p> : null}

            <button type="submit" className="action-button" disabled={submittingTitle || !providers.length}>
              {submittingTitle ? "Submitting task..." : "Generate titles"}
            </button>
          </form>
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Image translation"
            title="Run the second workflow"
            description="This workflow reuses the same task and project foundation, but now drives image-to-image translation."
          />

          <form className="form-grid" onSubmit={handleSubmitTranslationWorkflow}>
            <label>
              Provider
              <select
                value={translationForm.providerId}
                onChange={(event) =>
                  setTranslationForm((previous) => ({
                    ...previous,
                    providerId: event.target.value,
                  }))
                }
                required
              >
                <option value="">Select a provider</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Output language
              <select
                value={translationForm.imageLanguage}
                onChange={(event) =>
                  setTranslationForm((previous) => ({
                    ...previous,
                    imageLanguage: event.target.value,
                  }))
                }
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
                <option value="ja">日本語</option>
                <option value="fr">Français</option>
                <option value="es">Español</option>
              </select>
            </label>

            <label>
              Compliance mode
              <select
                value={translationForm.complianceMode}
                onChange={(event) =>
                  setTranslationForm((previous) => ({
                    ...previous,
                    complianceMode: event.target.value as "strict" | "balanced",
                  }))
                }
              >
                <option value="strict">Strict</option>
                <option value="balanced">Balanced</option>
              </select>
            </label>

            <label>
              Aspect ratio
              <select
                value={translationForm.aspectRatio}
                onChange={(event) =>
                  setTranslationForm((previous) => ({
                    ...previous,
                    aspectRatio: event.target.value,
                  }))
                }
              >
                <option value="1:1">1:1</option>
                <option value="4:5">4:5</option>
                <option value="3:4">3:4</option>
                <option value="16:9">16:9</option>
              </select>
            </label>

            <label className="span-2">
              Image model
              <input
                value={translationForm.imageModel}
                onChange={(event) =>
                  setTranslationForm((previous) => ({
                    ...previous,
                    imageModel: event.target.value,
                  }))
                }
              />
            </label>

            <div className="span-2 upload-card">
              <div className="upload-card-copy">
                <strong>Images to translate</strong>
                <p>Select one or more source images from local storage.</p>
                <span className="mono">
                  {selectedTranslateFiles.length
                    ? `${selectedTranslateFiles.length} file(s) selected`
                    : "No images selected"}
                </span>
              </div>
              <div className="hero-actions compact-actions">
                <button
                  type="button"
                  className="action-button secondary"
                  onClick={handleSelectTranslateFiles}
                >
                  Choose translation images
                </button>
                {selectedTranslateFiles.length ? (
                  <button
                    type="button"
                    className="action-button secondary"
                    onClick={() => setSelectedTranslateFiles([])}
                  >
                    Clear images
                  </button>
                ) : null}
              </div>
            </div>

            {translationError ? <p className="error-copy span-2">{translationError}</p> : null}

            <button
              type="submit"
              className="action-button"
              disabled={submittingTranslation || !providers.length}
            >
              {submittingTranslation ? "Submitting translation..." : "Translate images"}
            </button>
          </form>
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Quick generate"
            title="Create the third workflow"
            description="This creative generation flow uses the same task and project pipeline, but writes generated output images back into the project archive."
          />

          <form className="form-grid" onSubmit={handleSubmitQuickWorkflow}>
            <label>
              Provider
              <select
                value={quickForm.providerId}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    providerId: event.target.value,
                  }))
                }
                required
              >
                <option value="">Select a provider</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Quick mode
              <select
                value={quickForm.quickMode}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    quickMode: event.target.value as QuickGenerateFormState["quickMode"],
                  }))
                }
              >
                <option value="hero">Hero image</option>
                <option value="feature">Feature image</option>
                <option value="lifestyle">Lifestyle image</option>
              </select>
            </label>

            <label>
              Product name
              <input
                value={quickForm.productName}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    productName: event.target.value,
                  }))
                }
                required
              />
            </label>

            <label>
              Output language
              <select
                value={quickForm.outputLanguage}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    outputLanguage: event.target.value,
                  }))
                }
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
                <option value="ja">日本語</option>
                <option value="fr">Français</option>
                <option value="es">Español</option>
              </select>
            </label>

            <label className="span-2">
              Product detail
              <textarea
                value={quickForm.productDetail}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    productDetail: event.target.value,
                  }))
                }
                rows={5}
              />
            </label>

            <label>
              Aspect ratio
              <select
                value={quickForm.aspectRatio}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    aspectRatio: event.target.value,
                  }))
                }
              >
                <option value="1:1">1:1</option>
                <option value="4:5">4:5</option>
                <option value="3:4">3:4</option>
                <option value="16:9">16:9</option>
              </select>
            </label>

            <label>
              Output count
              <select
                value={quickForm.imageCount}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    imageCount: Number(event.target.value),
                  }))
                }
              >
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
                <option value={4}>4</option>
              </select>
            </label>

            <label className="span-2">
              Image model
              <input
                value={quickForm.imageModel}
                onChange={(event) =>
                  setQuickForm((previous) => ({
                    ...previous,
                    imageModel: event.target.value,
                  }))
                }
              />
            </label>

            <div className="span-2 upload-card">
              <div className="upload-card-copy">
                <strong>Reference images</strong>
                <p>Choose one or more reference images to guide the quick generation task.</p>
                <span className="mono">
                  {selectedQuickFiles.length
                    ? `${selectedQuickFiles.length} file(s) selected`
                    : "No images selected"}
                </span>
              </div>
              <div className="hero-actions compact-actions">
                <button
                  type="button"
                  className="action-button secondary"
                  onClick={handleSelectQuickFiles}
                >
                  Choose reference images
                </button>
                {selectedQuickFiles.length ? (
                  <button
                    type="button"
                    className="action-button secondary"
                    onClick={() => setSelectedQuickFiles([])}
                  >
                    Clear images
                  </button>
                ) : null}
              </div>
            </div>

            {quickError ? <p className="error-copy span-2">{quickError}</p> : null}

            <button
              type="submit"
              className="action-button"
              disabled={submittingQuick || !providers.length}
            >
              {submittingQuick ? "Submitting quick task..." : "Run quick generate"}
            </button>
          </form>
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Smart generate"
            title="Build grouped ecommerce image sets"
            description="This workflow creates a batch of different ecommerce image types from the same product inputs."
          />

          <form className="form-grid" onSubmit={handleSubmitSmartWorkflow}>
            <label>
              Provider
              <select
                value={smartForm.providerId}
                onChange={(event) =>
                  setSmartForm((previous) => ({
                    ...previous,
                    providerId: event.target.value,
                  }))
                }
                required
              >
                <option value="">Select a provider</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Product name
              <input
                value={smartForm.productName}
                onChange={(event) =>
                  setSmartForm((previous) => ({
                    ...previous,
                    productName: event.target.value,
                  }))
                }
                required
              />
            </label>

            <label className="span-2">
              Product detail
              <textarea
                value={smartForm.productDetail}
                onChange={(event) =>
                  setSmartForm((previous) => ({
                    ...previous,
                    productDetail: event.target.value,
                  }))
                }
                rows={5}
              />
            </label>

            <label>
              Output language
              <select
                value={smartForm.imageLanguage}
                onChange={(event) =>
                  setSmartForm((previous) => ({
                    ...previous,
                    imageLanguage: event.target.value,
                  }))
                }
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
                <option value="ja">日本語</option>
                <option value="fr">Français</option>
                <option value="es">Español</option>
              </select>
            </label>

            <label>
              Aspect ratio
              <select
                value={smartForm.aspectRatio}
                onChange={(event) =>
                  setSmartForm((previous) => ({
                    ...previous,
                    aspectRatio: event.target.value,
                  }))
                }
              >
                <option value="1:1">1:1</option>
                <option value="4:5">4:5</option>
                <option value="3:4">3:4</option>
                <option value="16:9">16:9</option>
              </select>
            </label>

            <label className="span-2">
              Image model
              <input
                value={smartForm.imageModel}
                onChange={(event) =>
                  setSmartForm((previous) => ({
                    ...previous,
                    imageModel: event.target.value,
                  }))
                }
              />
            </label>

            <div className="span-2 upload-card">
              <div className="upload-card-copy">
                <strong>Reference images</strong>
                <p>Choose product images that the smart workflow can analyze and reuse across outputs.</p>
                <span className="mono">
                  {selectedSmartFiles.length
                    ? `${selectedSmartFiles.length} file(s) selected`
                    : "No images selected"}
                </span>
              </div>
              <div className="hero-actions compact-actions">
                <button
                  type="button"
                  className="action-button secondary"
                  onClick={handleSelectSmartFiles}
                >
                  Choose smart images
                </button>
                {selectedSmartFiles.length ? (
                  <button
                    type="button"
                    className="action-button secondary"
                    onClick={() => setSelectedSmartFiles([])}
                  >
                    Clear images
                  </button>
                ) : null}
              </div>
            </div>

            <div className="span-2 smart-types-grid">
              {SMART_TYPE_OPTIONS.map((option) => (
                <label key={option.key} className="smart-type-card">
                  <span>{option.label}</span>
                  <select
                    value={smartTypeCounts[option.key] || 0}
                    onChange={(event) =>
                      setSmartTypeCounts((previous) => ({
                        ...previous,
                        [option.key]: Number(event.target.value),
                      }))
                    }
                  >
                    <option value={0}>0</option>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                    <option value={3}>3</option>
                  </select>
                </label>
              ))}
            </div>

            {smartError ? <p className="error-copy span-2">{smartError}</p> : null}

            <button
              type="submit"
              className="action-button"
              disabled={submittingSmart || !providers.length}
            >
              {submittingSmart ? "Submitting smart task..." : "Run smart generate"}
            </button>
          </form>
        </article>
      </section>

      <section className="workspace-grid">
        <article className="workspace-card">
          <SectionHeader
            eyebrow="Diagnostics"
            title="System summary"
            description="A quick read on providers, tasks, projects, and archived files from the local desktop database."
          />

          <div className="summary-grid">
            <div className="summary-card">
              <strong>{diagnostics?.providers_total ?? 0}</strong>
              <span>Providers</span>
            </div>
            <div className="summary-card">
              <strong>{diagnostics?.providers_enabled ?? 0}</strong>
              <span>Enabled</span>
            </div>
            <div className="summary-card">
              <strong>{diagnostics?.tasks_total ?? 0}</strong>
              <span>Tasks</span>
            </div>
            <div className="summary-card">
              <strong>{diagnostics?.tasks_failed ?? 0}</strong>
              <span>Failed tasks</span>
            </div>
            <div className="summary-card">
              <strong>{diagnostics?.projects_total ?? 0}</strong>
              <span>Projects</span>
            </div>
            <div className="summary-card">
              <strong>{diagnostics?.files_total ?? 0}</strong>
              <span>Archived files</span>
            </div>
          </div>
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Settings"
            title="Desktop defaults"
            description="Persist the main language and model defaults that the workflow forms should inherit."
          />

          <div className="form-grid">
            <label>
              Default title language
              <select
                value={defaultSettings.defaultTitleLanguage}
                onChange={(event) =>
                  handleSaveDefaultSetting("default_title_language", event.target.value)
                }
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
                <option value="ja">日本語</option>
                <option value="fr">Français</option>
                <option value="es">Español</option>
              </select>
            </label>
            <label>
              Default image language
              <select
                value={defaultSettings.defaultImageLanguage}
                onChange={(event) =>
                  handleSaveDefaultSetting("default_image_language", event.target.value)
                }
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
                <option value="ja">日本語</option>
                <option value="fr">Français</option>
                <option value="es">Español</option>
              </select>
            </label>
            <label>
              Default image model
              <input
                value={settingsDrafts.defaultModel}
                onChange={(event) =>
                  setSettingsDrafts((previous) => ({
                    ...previous,
                    defaultModel: event.target.value,
                  }))
                }
                onBlur={() => handleSaveDefaultSetting("default_model", settingsDrafts.defaultModel)}
              />
            </label>
            <label>
              Default title model
              <input
                value={settingsDrafts.defaultTitleModel}
                onChange={(event) =>
                  setSettingsDrafts((previous) => ({
                    ...previous,
                    defaultTitleModel: event.target.value,
                  }))
                }
                onBlur={() =>
                  handleSaveDefaultSetting("default_title_model", settingsDrafts.defaultTitleModel)
                }
              />
            </label>
            <label className="span-2">
              Default vision model
              <input
                value={settingsDrafts.defaultVisionModel}
                onChange={(event) =>
                  setSettingsDrafts((previous) => ({
                    ...previous,
                    defaultVisionModel: event.target.value,
                  }))
                }
                onBlur={() =>
                  handleSaveDefaultSetting(
                    "default_vision_model",
                    settingsDrafts.defaultVisionModel
                  )
                }
              />
            </label>
          </div>

          {settingsSaveMessage ? <p className="success-copy">{settingsSaveMessage}</p> : null}
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Task center"
            title="Live task polling"
            description="Tasks are now persisted in SQLite and updated by a background worker thread."
          />

          <div className="toolbar-row">
            <label className="inline-control">
              <span>State</span>
              <select
                value={projectStateFilter}
                onChange={(event) => setProjectStateFilter(event.target.value)}
              >
                <option value="active">Active</option>
                <option value="trashed">Trash</option>
                <option value="all">All</option>
              </select>
            </label>
            <label className="inline-control">
              <span>Status</span>
              <select
                value={taskStatusFilter}
                onChange={(event) => setTaskStatusFilter(event.target.value)}
              >
                <option value="all">All</option>
                <option value="queued">Queued</option>
                <option value="running">Running</option>
                <option value="succeeded">Succeeded</option>
                <option value="failed">Failed</option>
              </select>
            </label>
            <div className="summary-pills">
              <span className="micro-pill subtle">Tasks: {tasks.length}</span>
              <span className="micro-pill subtle">
                Running: {tasks.filter((task) => task.status === "running").length}
              </span>
              <span className="micro-pill subtle">
                Failed: {tasks.filter((task) => task.status === "failed").length}
              </span>
            </div>
          </div>

          <div className="collection-list">
            {filteredTasks.map((task) => (
              <button
                key={task.id}
                type="button"
                className={`collection-item tall selectable ${selectedTask?.id === task.id ? "selected" : ""}`}
                onClick={() => setSelectedTaskId(task.id)}
              >
                <div className="collection-meta">
                  <strong>{task.task_type}</strong>
                  <span>{task.current_step || "No current step"}</span>
                  <span className="mono">
                    {task.progress_done}/{task.progress_total}
                  </span>
                  {task.error_message ? <span className="error-copy">{task.error_message}</span> : null}
                </div>
                <div className="collection-side">
                  <StatusBadge status={task.status} />
                </div>
              </button>
            ))}
            {!filteredTasks.length ? <p className="muted-copy">No tasks match the current filter.</p> : null}
          </div>

          <div className="events-panel">
            <h3>Latest task events</h3>
            {taskEvents.length ? (
              taskEvents.map((event) => (
                <div key={event.id} className="event-row">
                  <span className={`event-dot event-${event.level}`} />
                  <div>
                    <strong>{event.event_type}</strong>
                    <p>{event.message}</p>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted-copy">Task events will appear here once a workflow runs.</p>
            )}
          </div>
        </article>

        <article className="workspace-card">
          <SectionHeader
            eyebrow="Project center"
            title="Archived title results"
            description="The first workflow now writes project files into the desktop app data directory."
          />

          <div className="toolbar-row">
            <label className="inline-control">
              <span>Status</span>
              <select
                value={projectStatusFilter}
                onChange={(event) => setProjectStatusFilter(event.target.value)}
              >
                <option value="all">All</option>
                <option value="queued">Queued</option>
                <option value="running">Running</option>
                <option value="succeeded">Succeeded</option>
                <option value="failed">Failed</option>
              </select>
            </label>
            <label className="inline-control grow">
              <span>Search</span>
              <input
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                placeholder="Search project summary"
              />
            </label>
          </div>

          <div className="collection-list">
            {filteredProjects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={`collection-item tall selectable ${selectedProject?.id === project.id ? "selected" : ""}`}
                onClick={() => setSelectedProjectId(project.id)}
              >
                <div className="collection-meta">
                  <strong>{project.summary}</strong>
                  <span>{project.status}</span>
                  <span className="mono">{project.id}</span>
                </div>
                <div className="collection-side">
                  <button
                    type="button"
                    className="text-button"
                    onClick={(event) => {
                      event.stopPropagation();
                      window.desktop.openPath(project.artifact_dir);
                    }}
                  >
                    Open
                  </button>
                </div>
              </button>
            ))}
            {!filteredProjects.length ? <p className="muted-copy">No projects match the current filters.</p> : null}
          </div>

          <div className="project-preview">
            <h3>Latest project preview</h3>
            {projectDetail ? (
              <>
                <p className="mono">{projectDetail.artifact_dir}</p>
                <div className="hero-actions compact-actions">
                  {projectDetail.record_state === "active" ? (
                    <button
                      type="button"
                      className="action-button secondary"
                      onClick={() => handleProjectAction(projectDetail.id, "trash")}
                    >
                      Move to trash
                    </button>
                  ) : null}
                  {projectDetail.record_state === "trashed" ? (
                    <>
                      <button
                        type="button"
                        className="action-button secondary"
                        onClick={() => handleProjectAction(projectDetail.id, "restore")}
                      >
                        Restore
                      </button>
                      <button
                        type="button"
                        className="action-button secondary danger-button"
                        onClick={() => handleProjectAction(projectDetail.id, "purge")}
                      >
                        Delete forever
                      </button>
                    </>
                  ) : null}
                </div>
                <div className="preview-grid">
                  <pre>
                    {projectPreviewText || "No text preview available for this project yet."}
                  </pre>
                  <div className="image-preview-card">
                    {projectPreviewImage ? (
                      <img src={projectPreviewImage} alt="Project preview" className="preview-image" />
                    ) : (
                      <p className="muted-copy">No image preview available yet.</p>
                    )}
                  </div>
                </div>
                <div className="file-list">
                  {projectDetail.files.map((file) => (
                    <div key={file.id} className="file-row">
                      <div>
                        <strong>{file.file_name}</strong>
                        <p>{file.file_role}</p>
                      </div>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => window.desktop.openPath(file.file_path)}
                      >
                        Open
                      </button>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted-copy">Run a title workflow to create the first archived project.</p>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}
