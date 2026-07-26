#!/bin/bash
# TuLite 一键启动脚本（双击运行）
cd "$(dirname "$0")"

echo "==> 清理 git 残留锁文件（如有）..."
rm -f .git/*.lock .git/refs/remotes/cnb/main.lock 2>/dev/null

# 检查 streamlit，没有则安装（兼容 Homebrew Python 的 externally-managed 限制）
if ! python3 -c "import streamlit" 2>/dev/null; then
  echo "==> 首次运行，安装依赖（约1-2分钟）..."
  python3 -m pip install -r requirements.txt 2>/dev/null \
    || python3 -m pip install --break-system-packages -r requirements.txt \
    || { echo "依赖安装失败，请截图此窗口"; read -p "按回车退出"; exit 1; }
fi

echo "==> 启动 TuLite，浏览器将自动打开 http://localhost:8501"
echo "==> 停止：按 Ctrl+C 或关闭本窗口"
python3 -m streamlit run app.py
