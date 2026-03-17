@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ╔══════════════════════════════════════════════════════════════╗
echo ║       🍌 TEMU 电商智能作图系统 V15.0 部署脚本 (Windows)     ║
echo ║                                                              ║
echo ║       核心作者: 企鹅 ^& 小明                                  ║
echo ║       商业订阅: 企鹅 ^& Jerry                                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 检查 Docker
echo [1/5] 检查 Docker 环境...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未安装
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✅ Docker 已安装

docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Docker Compose 未安装
        pause
        exit /b 1
    )
)
echo ✅ Docker Compose 已安装

:: 准备环境
echo.
echo [2/5] 准备环境配置...
if not exist .env (
    copy .env.example .env >nul
    echo ✅ 已创建 .env 配置文件
) else (
    echo ✅ .env 配置文件已存在
)

if not exist data mkdir data
if not exist data\files mkdir data\files
echo ✅ 数据目录已创建

:: 构建镜像
echo.
echo [3/5] 构建 Docker 镜像...
docker-compose build --no-cache
if errorlevel 1 (
    echo ❌ 镜像构建失败
    pause
    exit /b 1
)
echo ✅ 镜像构建完成

:: 启动服务
echo.
echo [4/5] 启动服务...
docker-compose up -d
if errorlevel 1 (
    echo ❌ 服务启动失败
    pause
    exit /b 1
)
echo ✅ 服务已启动

:: 等待并检查
echo.
echo [5/5] 检查服务状态...
timeout /t 5 /nobreak >nul

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    🎉 部署成功！                             ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║                                                              ║
echo ║  访问地址: http://localhost:8501                             ║
echo ║                                                              ║
echo ║  默认密码:                                                   ║
echo ║    用户密码: eee666                                          ║
echo ║    管理员密码: joolhome@2023                                 ║
echo ║                                                              ║
echo ║  首次使用请在管理后台配置 API Key 或使用自己的 Key           ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 询问是否打开浏览器
set /p open_browser="是否打开浏览器访问? (y/n): "
if /i "%open_browser%"=="y" (
    start http://localhost:8501
)

pause
