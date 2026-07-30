#!/bin/bash
# TuLite 一键启动脚本（双击运行）
cd "$(dirname "$0")"

dependency_probe() {
  python3 - <<'PY'
import importlib
import re

streamlit = importlib.import_module("streamlit")


def version_tuple(value):
    numbers = [int(part) for part in re.findall(r"\d+", str(value))[:3]]
    return tuple((numbers + [0, 0, 0])[:3])


if version_tuple(getattr(streamlit, "__version__", "0")) < (1, 50, 0):
    raise RuntimeError("Streamlit 1.50 or newer is required")

for module in (
    "PIL",
    "google.genai",
    "httpx",
    "socksio",
    "boto3",
    "webview",
    "cryptography",
):
    importlib.import_module(module)
PY
}

if [ "${TULITE_DEPENDENCY_PROBE_ONLY:-0}" = "1" ]; then
  dependency_probe
  exit $?
fi

# 检查完整运行时依赖和最低版本（兼容 Homebrew Python 的 externally-managed 限制）
if ! dependency_probe 2>/dev/null; then
  echo "==> 首次运行，安装依赖（约1-2分钟）..."
  python3 -m pip install -r requirements.txt 2>/dev/null \
    || python3 -m pip install --break-system-packages -r requirements.txt \
    || { echo "依赖安装失败，请截图此窗口"; read -p "按回车退出"; exit 1; }
fi

echo "==> 启动 TuLite，浏览器将自动打开 http://localhost:8501"
echo "==> 停止：按 Ctrl+C 或关闭本窗口"
python3 run_tulite.py
