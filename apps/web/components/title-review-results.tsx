type UnknownRecord = Record<string, unknown>

type NormalizedTitlePair = {
  index: number
  english: string
  chinese: string
  reviewLabel: string
  reviewSummary: string
  reviewNotes: string[]
  englishCharCount: number
  withinRange: boolean | null
  minChars: number | null
  maxChars: number | null
}

type TitleReviewResultsProps = {
  titlePairsSource: unknown
  fallbackTitlesSource?: unknown
  warningsSource?: unknown
  emptyMessage: string
  fallbackHeading?: string
}

function readRecord(value: unknown) {
  if (!value || typeof value !== "object") {
    return null
  }

  return value as UnknownRecord
}

function readString(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}

function readStringArray(value: unknown) {
  return Array.isArray(value)
    ? value.map((item) => readString(item)).filter(Boolean)
    : []
}

function readObjectArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is UnknownRecord => Boolean(item) && typeof item === "object")
    : []
}

function readNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  return null
}

function readBoolean(value: unknown) {
  if (typeof value === "boolean") {
    return value
  }

  if (typeof value === "string") {
    if (value === "true") {
      return true
    }
    if (value === "false") {
      return false
    }
  }

  return null
}

function pickString(records: UnknownRecord[], keys: string[]) {
  for (const record of records) {
    for (const key of keys) {
      const value = readString(record[key])
      if (value) {
        return value
      }
    }
  }

  return ""
}

function pickNumber(records: UnknownRecord[], keys: string[]) {
  for (const record of records) {
    for (const key of keys) {
      const value = readNumber(record[key])
      if (typeof value === "number") {
        return value
      }
    }
  }

  return null
}

function pickBoolean(records: UnknownRecord[], keys: string[]) {
  for (const record of records) {
    for (const key of keys) {
      const value = readBoolean(record[key])
      if (typeof value === "boolean") {
        return value
      }
    }
  }

  return null
}

function collectNotes(records: UnknownRecord[]) {
  const noteKeys = [
    "review_notes",
    "reviewNotes",
    "notes",
    "warnings",
    "issues",
    "suggestions",
    "reasons",
    "comments",
  ]
  const merged = new Set<string>()

  for (const record of records) {
    for (const key of noteKeys) {
      for (const value of readStringArray(record[key])) {
        merged.add(value)
      }
      const stringValue = readString(record[key])
      if (stringValue) {
        merged.add(stringValue)
      }
    }
  }

  return Array.from(merged)
}

function normalizeTitlePair(pair: UnknownRecord, index: number): NormalizedTitlePair {
  const reviewRecord = readRecord(pair.review)
  const complianceRecord = readRecord(pair.compliance)
  const metricRecord = readRecord(pair.metrics)
  const records = [pair, reviewRecord, complianceRecord, metricRecord].filter(
    (item): item is UnknownRecord => Boolean(item),
  )

  const english = pickString(records, [
    "english_title",
    "english",
    "en_title",
    "en",
    "title_en",
    "titleEnglish",
    "output_en",
    "title",
  ])
  const chinese = pickString(records, [
    "chinese_title",
    "chinese",
    "zh_title",
    "zh",
    "title_zh",
    "titleChinese",
    "output_zh",
  ])
  const reviewLabel = pickString(records, [
    "review_label",
    "reviewLabel",
    "verdict",
    "label",
    "status",
    "compliance_label",
    "rating",
  ])
  const reviewSummary = pickString(records, [
    "review_summary",
    "reviewSummary",
    "summary",
    "feedback",
    "comment",
    "rationale",
  ])
  const minChars = pickNumber(records, [
    "min_chars",
    "recommended_min_chars",
    "min_length",
    "minimum_length",
  ])
  const maxChars = pickNumber(records, [
    "max_chars",
    "recommended_max_chars",
    "max_length",
    "maximum_length",
  ])
  const measuredCount = pickNumber(records, [
    "english_char_count",
    "englishCharCount",
    "char_count",
    "charCount",
    "english_length",
    "length",
  ])
  const englishCharCount = measuredCount ?? english.length
  const withinRange =
    pickBoolean(records, [
      "within_range",
      "withinRange",
      "english_within_range",
      "englishWithinRange",
      "char_count_within_range",
      "charCountWithinRange",
      "is_within_range",
      "isWithinRange",
    ]) ??
    (typeof minChars === "number" && typeof maxChars === "number"
      ? englishCharCount >= minChars && englishCharCount <= maxChars
      : null)

  return {
    index,
    english,
    chinese,
    reviewLabel,
    reviewSummary,
    reviewNotes: collectNotes(records),
    englishCharCount,
    withinRange,
    minChars,
    maxChars,
  }
}

function getReviewTone(label: string, withinRange: boolean | null) {
  const normalizedLabel = label.toLowerCase()

  if (
    normalizedLabel.includes("不") ||
    normalizedLabel.includes("fail") ||
    normalizedLabel.includes("risk") ||
    normalizedLabel.includes("reject") ||
    withinRange === false
  ) {
    return "rose"
  }

  if (
    normalizedLabel.includes("warn") ||
    normalizedLabel.includes("注意") ||
    normalizedLabel.includes("优化") ||
    normalizedLabel.includes("revise")
  ) {
    return "amber"
  }

  if (
    normalizedLabel.includes("通过") ||
    normalizedLabel.includes("合规") ||
    normalizedLabel.includes("pass") ||
    normalizedLabel.includes("good") ||
    withinRange === true
  ) {
    return "emerald"
  }

  return "slate"
}

function getBadgeClass(tone: string) {
  if (tone === "emerald") {
    return "bg-emerald-50 text-emerald-700 ring-emerald-200"
  }

  if (tone === "rose") {
    return "bg-rose-50 text-rose-700 ring-rose-200"
  }

  if (tone === "amber") {
    return "bg-amber-50 text-amber-700 ring-amber-200"
  }

  return "bg-slate-100 text-slate-600 ring-slate-200"
}

function formatCharCount(pair: NormalizedTitlePair) {
  if (pair.withinRange === true && typeof pair.minChars === "number" && typeof pair.maxChars === "number") {
    return `${pair.englishCharCount} 字 · ${pair.minChars}-${pair.maxChars} 范围内`
  }

  if (pair.withinRange === false && typeof pair.minChars === "number" && typeof pair.maxChars === "number") {
    return `${pair.englishCharCount} 字 · 超出 ${pair.minChars}-${pair.maxChars}`
  }

  if (pair.withinRange === true) {
    return `${pair.englishCharCount} 字 · 字数合规`
  }

  if (pair.withinRange === false) {
    return `${pair.englishCharCount} 字 · 超出建议范围`
  }

  return `${pair.englishCharCount} 字 · 未返回范围判定`
}

function buildCopyAllValue(titlePairs: NormalizedTitlePair[]) {
  return titlePairs
    .map((pair) => {
      const lines = [
        `${pair.index + 1}. EN: ${pair.english || "未返回"}`,
        `CN: ${pair.chinese || "未返回"}`,
        `Review: ${pair.reviewLabel || "待复核"}`,
        `Chars: ${formatCharCount(pair)}`,
      ]

      if (pair.reviewSummary) {
        lines.push(`Summary: ${pair.reviewSummary}`)
      }

      if (pair.reviewNotes.length > 0) {
        lines.push(`Notes: ${pair.reviewNotes.join("；")}`)
      }

      return lines.join("\n")
    })
    .join("\n\n")
}

export function TitleReviewResults({
  titlePairsSource,
  fallbackTitlesSource,
  warningsSource,
  emptyMessage,
  fallbackHeading = "英文标题候选",
}: TitleReviewResultsProps) {
  const hasTitlePairsPayload = Array.isArray(titlePairsSource)
  const titlePairs = readObjectArray(titlePairsSource)
    .map(normalizeTitlePair)
    .filter(
      (pair) =>
        Boolean(pair.english) ||
        Boolean(pair.chinese) ||
        Boolean(pair.reviewLabel) ||
        Boolean(pair.reviewSummary) ||
        pair.reviewNotes.length > 0,
    )
  const fallbackTitles = readStringArray(fallbackTitlesSource)
  const warnings = readStringArray(warningsSource)
  const copyAllValue = buildCopyAllValue(titlePairs)

  return (
    <div className="space-y-4">
      {titlePairs.length > 0 ? (
        <>
          <div className="space-y-3">
            {titlePairs.map((pair) => {
              const tone = getReviewTone(pair.reviewLabel, pair.withinRange)
              const badgeClassName = getBadgeClass(tone)
              return (
                <div key={`${pair.index}-${pair.english}-${pair.chinese}`} className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                      候选 {String(pair.index + 1).padStart(2, "0")}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ${badgeClassName}`}>
                        {pair.reviewLabel || "待复核"}
                      </span>
                      <span className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ${getBadgeClass(pair.withinRange === null ? "slate" : pair.withinRange ? "emerald" : "rose")}`}>
                        {formatCharCount(pair)}
                      </span>
                    </div>
                  </div>

                  {pair.reviewSummary ? (
                    <p className="mt-3 text-sm leading-6 text-slate-600">{pair.reviewSummary}</p>
                  ) : null}

                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">English</p>
                      <p className="mt-3 text-sm leading-7 text-slate-900">{pair.english || "未返回英文标题。"}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">中文参考</p>
                      <p className="mt-3 text-sm leading-7 text-slate-900">{pair.chinese || "未返回中文标题。"}</p>
                    </div>
                  </div>

                  {pair.reviewNotes.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {pair.reviewNotes.map((note, index) => (
                        <span key={`${note}-${index}`} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                          {note}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">成对复制输出</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">保留 EN/CN 配对与复核信息，便于整体拷走继续审阅。</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {titlePairs.length} 组
              </span>
            </div>
            <textarea
              readOnly
              value={copyAllValue}
              rows={Math.min(Math.max(titlePairs.length * 5, 8), 20)}
              className="mt-4 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700 outline-none"
            />
          </div>
        </>
      ) : !hasTitlePairsPayload && fallbackTitles.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-slate-900">{fallbackHeading}</p>
          {fallbackTitles.map((title, index) => (
            <div key={`${title}-${index}`} className="rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-800">
              {index + 1}. {title}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm leading-7 text-slate-500">{emptyMessage}</p>
      )}

      {warnings.length > 0 ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {warnings.map((warning, index) => (
            <p key={`${warning}-${index}`}>- {warning}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
