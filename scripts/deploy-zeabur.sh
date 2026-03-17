#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-temu-v15}"
SERVICE_NAME="${SERVICE_NAME:-temu-image-gen}"
SERVICE_ID="${SERVICE_ID:-}"
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-}"
REGION="${REGION:-}"
FULL_CONTEXT=0

usage() {
  cat <<'EOF'
用法:
  ZEABUR_TOKEN=xxx ./scripts/deploy-zeabur.sh [选项]

选项:
  --project <name>   项目名（默认: temu-v15）
  --service <name>   服务名（默认: temu-image-gen）
  --service-id <id>  可选，指定服务ID（最快，推荐后续更新）
  --domain <domain>  可选，部署后绑定自定义域名
  --region <region>  可选，新建项目时使用
  --full             使用完整目录部署（默认会自动瘦身上传上下文）
  -h, --help         显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --service)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --service-id)
      SERVICE_ID="$2"
      shift 2
      ;;
    --domain)
      CUSTOM_DOMAIN="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --full)
      FULL_CONTEXT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${ZEABUR_TOKEN:-}" ]]; then
  echo "❌ 未设置 ZEABUR_TOKEN"
  echo "示例: ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh"
  exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "❌ 未检测到 npx，请先安装 Node.js (>=18)"
  exit 1
fi

if ! command -v rg >/dev/null 2>&1; then
  echo "❌ 未检测到 rg (ripgrep)，请先安装"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "❌ 未检测到 rsync，请先安装"
  exit 1
fi

strip_ansi() {
  sed -E 's/\x1B\[[0-9;]*[mK]//g'
}

zb() {
  npx -y zeabur --interactive=false "$@"
}

zbi() {
  npx -y zeabur "$@"
}

run_ni() {
  local output
  output="$(zb "$@" 2>&1 || true)"
  echo "$output"
  if echo "$output" | strip_ansi | rg -q '(^|\s)ERROR\b'; then
    return 1
  fi
  return 0
}

get_project_id_by_name() {
  local name="$1"
  local out
  out="$(run_ni project list || true)"
  echo "$out" | strip_ansi | awk -v n="$name" '$2==n {print $1; exit}'
}

get_service_id_by_name_or_single() {
  local name="$1"
  local out
  out="$(run_ni service list || true)"
  local matched
  matched="$(echo "$out" | strip_ansi | awk -v n="$name" '$2==n {print $1; exit}')"
  if [[ -n "$matched" ]]; then
    echo "$matched"
    return 0
  fi
  local count
  count="$(echo "$out" | strip_ansi | awk '$1 ~ /^[a-f0-9]{24}$/ {c++} END {print c+0}')"
  if [[ "$count" -eq 1 ]]; then
    echo "$out" | strip_ansi | awk '$1 ~ /^[a-f0-9]{24}$/ {print $1; exit}'
    return 0
  fi
  return 1
}

SRC_DIR="$(pwd)"
WORK_DIR="$SRC_DIR"

if [[ "$FULL_CONTEXT" -eq 0 ]]; then
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  rsync -a "$SRC_DIR"/ "$TMP_DIR"/ \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude 'venv/' \
    --exclude 'env/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '.mypy_cache/' \
    --exclude '.DS_Store' \
    --exclude 'data/' \
    --exclude 'nginx/' \
    --exclude '*.zip' \
    --exclude '*.xlsx' \
    --exclude 'deploy.bat' \
    --exclude 'deploy.sh' \
    --exclude 'scripts/install-docker.sh'

  mkdir -p "$TMP_DIR/data"
  WORK_DIR="$TMP_DIR"
  echo "ℹ️ 使用瘦身上下文部署，加快上传速度"
fi

echo "🔐 登录 Zeabur CLI..."
zb auth login --token "$ZEABUR_TOKEN" >/dev/null

echo "📦 检查项目: $PROJECT_NAME"
PROJECT_ID="$(get_project_id_by_name "$PROJECT_NAME" || true)"

if [[ -z "$PROJECT_ID" ]]; then
  echo "➕ 项目不存在，准备创建: $PROJECT_NAME"
  if [[ -n "$REGION" ]]; then
    run_ni project create --name "$PROJECT_NAME" --region "$REGION" >/dev/null || true
  else
    echo "ℹ️ 将进入交互式项目创建（需选 region，仅首次）"
    zbi project create --name "$PROJECT_NAME"
  fi
  PROJECT_ID="$(get_project_id_by_name "$PROJECT_NAME" || true)"
fi

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ 无法获取项目ID，请检查项目名或手动创建后重试"
  exit 1
fi

run_ni context set project --id "$PROJECT_ID" --yes >/dev/null || true

cd "$WORK_DIR"

if [[ -z "$SERVICE_ID" ]]; then
  SERVICE_ID="$(get_service_id_by_name_or_single "$SERVICE_NAME" || true)"
fi

if [[ -n "$SERVICE_ID" ]]; then
  echo "🚀 检测到服务已存在，直接发布更新: $SERVICE_NAME"
  zb deploy --service-id "$SERVICE_ID"
else
  echo "🚀 首次部署：将进入一次交互式创建服务"
  zbi deploy --create --name "$SERVICE_NAME"
  SERVICE_ID="$(get_service_id_by_name_or_single "$SERVICE_NAME" || true)"
fi

if [[ -n "$CUSTOM_DOMAIN" ]]; then
  echo "🌐 绑定域名: $CUSTOM_DOMAIN"
  if [[ -n "$SERVICE_ID" ]]; then
    zb domain create --id "$SERVICE_ID" --domain "$CUSTOM_DOMAIN" --yes || true
  else
    zb domain create --name "$SERVICE_NAME" --domain "$CUSTOM_DOMAIN" --yes || true
  fi
fi

echo "✅ 部署完成"
echo "---- 服务信息 ----"
if [[ -n "$SERVICE_ID" ]]; then
  zb service get --id "$SERVICE_ID" || true
else
  zb service get --name "$SERVICE_NAME" || true
fi
echo "---- 域名信息 ----"
if [[ -n "$SERVICE_ID" ]]; then
  zb domain list --id "$SERVICE_ID" || true
else
  zb domain list --name "$SERVICE_NAME" || true
fi
