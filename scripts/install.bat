@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo Claude Proxy Router 一键安装脚本
echo ========================================
echo.

:: 检测 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 获取 Python 版本
for /f "delims=" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo 检测到: %PYTHON_VERSION%

:: 设置 pip 镜像（国内网络优化）
set PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_INDEX_URL=%PIP_MIRROR%

echo.
echo [1/4] 正在更新 pip...
python -m pip install --upgrade pip -i %PIP_MIRROR% --quiet

echo.
echo [2/4] 正在安装 Claude Proxy Router...
pip install claude-mux -i %PIP_MIRROR%
if errorlevel 1 (
    echo [错误] 安装失败，尝试使用官方源...
    pip install claude-mux
    if errorlevel 1 (
        echo [错误] 安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

echo.
echo [3/4] 正在生成配置文件...
:: 检查是否已有 .env
if exist ".env" (
    echo 发现已有 .env 文件，跳过创建
) else (
    copy .env.example .env >nul 2>&1
    if exist ".env" (
        echo 已创建 .env 配置文件，请编辑设置 AUTH_TOKEN
    ) else (
        echo [警告] 未找到 .env.example，创建默认配置
        (
            echo AUTH_TOKEN=sk-proxy-change-me
            echo DEFAULT_UPSTREAM=https://api.anthropic.com
            echo SERVER_PORT=12346
        ) > .env
    )
)

echo.
echo [4/4] 安装完成！
echo.
echo ========================================
echo 快速开始:
echo.
echo 1. 编辑 .env 文件设置 AUTH_TOKEN
echo 2. 运行: claude-mux
echo    或: python -m main
echo.
echo 详细文档: see README.md
echo ========================================
pause