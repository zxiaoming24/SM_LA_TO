@echo off
chcp 65001 >nul
echo ========================================
echo   Live2D 模型展示 - 启动服务器
echo ========================================
echo.

REM 检查 Python 是否安装
where python >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 检测到 Python
    echo.
    echo 正在启动服务器...
    echo 请在浏览器中访问: http://localhost:8080
    echo.
    echo 按 Ctrl+C 停止服务器
    echo.
    python -m http.server 8080
    goto :end
)

REM 检查 Node.js 是否安装
where node >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 检测到 Node.js
    echo.
    
    REM 检查 http-server 是否安装
    where http-server >nul 2>&1
    if %errorlevel% neq 0 (
        echo [!] 未检测到 http-server，正在安装...
        npm install -g http-server
    )
    
    echo 正在启动服务器...
    echo 请在浏览器中访问: http://localhost:8080
    echo.
    echo 按 Ctrl+C 停止服务器
    echo.
    http-server -p 8080
    goto :end
)

echo [✗] 未检测到 Python 或 Node.js
echo.
echo 请安装以下任一软件：
echo   1. Python 3.x - https://www.python.org/downloads/
echo   2. Node.js - https://nodejs.org/
echo.
echo 或者手动使用其他 HTTP 服务器
echo.
pause

:end
