@echo off
chcp 65001 >nul
setlocal

echo 电商出图工作台 self-hosted 单机版
echo.

if not exist .env (
  copy .env.example .env >nul
  echo 已创建 .env
)

if not exist data mkdir data
if not exist data\files mkdir data\files
if not exist data\projects mkdir data\projects

docker compose up -d --build
if errorlevel 1 (
  echo 启动失败，请检查 Docker Desktop。
  pause
  exit /b 1
)

echo.
echo 启动完成: http://localhost:8501
pause

