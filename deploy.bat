@echo off
chcp 65001 >nul
setlocal

echo 电商出图工作台 self-hosted 单机版
echo.

if not exist .env (
  copy .env.example .env >nul
  echo 已创建 .env
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo 未找到 Docker Compose，请先启动或安装 Docker Desktop。
  pause
  exit /b 1
)

docker compose config --quiet
if errorlevel 1 (
  echo 部署配置无效，请先在 .env 中设置 APP_ACCESS_PASSWORD 并修正上方错误。
  pause
  exit /b 1
)

if not exist data mkdir data
if not exist data\files mkdir data\files
if not exist data\projects mkdir data\projects

docker compose up -d --build
if errorlevel 1 (
  echo 启动失败，请检查上方 Docker Compose 错误。
  pause
  exit /b 1
)

echo.
echo 启动完成: http://localhost:8501
pause
