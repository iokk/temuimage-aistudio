"use client"

import { useState } from "react"
import { useEffect } from "react"


type ProjectState = {
  project_id: string
  project_name: string
  project_slug: string
  project_status: string
} | null

type ProjectsResponse = {
  items: NonNullable<ProjectState>[]
  current_project: ProjectState
}

export function CurrentProjectPanel({
  initialProject,
  isAdmin,
}: {
  initialProject: ProjectState
  isAdmin: boolean
}) {
  const [project, setProject] = useState<ProjectState>(initialProject)
  const [projects, setProjects] = useState<NonNullable<ProjectState>[]>(
    initialProject ? [initialProject] : [],
  )
  const [name, setName] = useState(initialProject?.project_name || "")
  const [newProjectName, setNewProjectName] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [isSelecting, setIsSelecting] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  useEffect(() => {
    let cancelled = false

    async function loadProjects() {
      try {
        const response = await fetch("/api/platform/projects", { cache: "no-store" })
        if (!response.ok) {
          throw new Error("项目列表获取失败，请稍后刷新。")
        }
        const payload = (await response.json()) as ProjectsResponse
        if (cancelled) {
          return
        }
        setProjects(payload.items || [])
        setProject(payload.current_project || null)
        setName(payload.current_project?.project_name || "")
      } catch {
        if (!cancelled) {
          setError((current) => current || "项目列表获取失败，请稍后刷新。")
        }
      }
    }

    void loadProjects()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSelect(projectId: string) {
    setIsSelecting(true)
    setError("")
    setSuccess("")

    try {
      const response = await fetch("/api/platform/projects/current/select", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId }),
      })
      if (!response.ok) {
        throw new Error("当前项目切换失败，请稍后重试。")
      }
      const payload = (await response.json()) as ProjectsResponse
      setProjects(payload.items || [])
      setProject(payload.current_project || null)
      setName(payload.current_project?.project_name || "")
      setSuccess("当前项目已切换。")
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "当前项目切换失败，请稍后重试。",
      )
    } finally {
      setIsSelecting(false)
    }
  }

  async function handleCreate() {
    if (!isAdmin) {
      return
    }

    const normalizedName = newProjectName.trim()
    if (!normalizedName) {
      setError("请输入新项目名称后再创建。")
      setSuccess("")
      return
    }

    setIsCreating(true)
    setError("")
    setSuccess("")

    try {
      const response = await fetch("/api/platform/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: normalizedName }),
      })
      if (!response.ok) {
        throw new Error("项目创建失败，请稍后重试。")
      }
      const payload = (await response.json()) as ProjectsResponse
      setProjects(payload.items || [])
      setProject(payload.current_project || null)
      setName(payload.current_project?.project_name || normalizedName)
      setNewProjectName("")
      setSuccess("新项目已创建，并已切换为当前项目。")
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "项目创建失败，请稍后重试。",
      )
    } finally {
      setIsCreating(false)
    }
  }

  async function handleSave() {
    if (!isAdmin) {
      return
    }

    const normalizedName = name.trim()
    if (!normalizedName) {
      setError("请输入项目名称后再保存。")
      setSuccess("")
      return
    }

    setIsSaving(true)
    setError("")
    setSuccess("")

    try {
      const response = await fetch("/api/platform/projects/current", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: normalizedName }),
      })
      if (!response.ok) {
        throw new Error("默认项目更新失败，请稍后重试。")
      }
      const payload = (await response.json()) as { project: ProjectState }
      setProject(payload.project)
      setProjects((current) =>
        current.map((item) =>
          item.project_id === payload.project?.project_id
            ? {
                ...item,
                project_name: payload.project?.project_name || item.project_name,
              }
            : item,
        ),
      )
      setName(payload.project?.project_name || normalizedName)
      setSuccess("默认项目已更新。")
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "默认项目更新失败，请稍后重试。",
      )
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <h3 className="text-xl font-bold text-slate-950">当前项目管理</h3>
      <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
        <label className="block text-sm font-medium text-slate-800">
          当前项目
          <select
            value={project?.project_id || ""}
            onChange={(event) => void handleSelect(event.target.value)}
            disabled={isSelecting || projects.length === 0}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 disabled:bg-slate-50 disabled:text-slate-400"
          >
            {projects.map((item) => (
              <option key={item.project_id} value={item.project_id}>
                {item.project_name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium text-slate-800">
          当前项目名称
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!isAdmin || isSaving}
            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 disabled:bg-slate-50 disabled:text-slate-400"
          />
        </label>
        <p>项目标识：{project?.project_slug || "未记录"}</p>
        <p>项目状态：{project?.project_status || "active"}</p>
        <p>项目数量：{projects.length}</p>
        {!isAdmin ? <p>当前仅管理员可以修改默认项目名称。</p> : null}
      </div>

      {isAdmin ? (
        <div className="mt-6 space-y-4">
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="rounded-2xl bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isSaving ? "保存中..." : "保存当前项目"}
          </button>

          <div className="rounded-2xl border border-slate-200 p-4">
            <p className="text-sm font-medium text-slate-800">创建新项目</p>
            <input
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
              disabled={isCreating}
              className="mt-3 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 disabled:bg-slate-50 disabled:text-slate-400"
              placeholder="例如：Summer Campaign"
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={isCreating}
              className="mt-3 rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:bg-sky-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
            >
              {isCreating ? "创建中..." : "创建并切换项目"}
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      ) : null}
    </div>
  )
}
