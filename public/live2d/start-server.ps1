# Live2D 模型展示 - PowerShell 启动脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Live2D 模型展示 - 启动服务器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    Write-Host "[✓] 检测到 Python" -ForegroundColor Green
    Write-Host ""
    Write-Host "正在启动服务器..." -ForegroundColor Yellow
    Write-Host "请在浏览器中访问: http://localhost:8080" -ForegroundColor Green
    Write-Host ""
    Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
    Write-Host ""
    
    python -m http.server 8080
    exit
}

# 检查 Node.js
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "[✓] 检测到 Node.js" -ForegroundColor Green
    Write-Host ""
    
    # 检查 http-server
    $httpServer = Get-Command http-server -ErrorAction SilentlyContinue
    if (-not $httpServer) {
        Write-Host "[!] 未检测到 http-server，正在安装..." -ForegroundColor Yellow
        npm install -g http-server
    }
    
    Write-Host "正在启动服务器..." -ForegroundColor Yellow
    Write-Host "请在浏览器中访问: http://localhost:8080" -ForegroundColor Green
    Write-Host ""
    Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
    Write-Host ""
    
    http-server -p 8080
    exit
}

Write-Host "[✗] 未检测到 Python 或 Node.js" -ForegroundColor Red
Write-Host ""
Write-Host "请安装以下任一软件：" -ForegroundColor Yellow
Write-Host "  1. Python 3.x - https://www.python.org/downloads/" -ForegroundColor White
Write-Host "  2. Node.js - https://nodejs.org/" -ForegroundColor White
Write-Host ""
Write-Host "或者手动使用其他 HTTP 服务器" -ForegroundColor White
Write-Host ""
Pause
