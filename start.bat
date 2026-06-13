@echo off
title 先行一步 (One Step Ahead) - 一鍵啟動
echo ==========================================
echo    先行一步 (One Step Ahead) 啟動中...
echo ==========================================

cd /d %~dp0

REM 檢查虛擬環境
if not exist "venv" (
    echo ❌ 錯誤: 找不到 venv 虛擬環境。
    echo 請先執行環境設定:
    echo python -m venv venv
    echo .\venv\Scripts\activate
    echo pip install -r pi/requirements.txt
    pause
    exit /b
)

REM 啟動 Web 儀表板 (在另一個隱藏背景中)
echo [1/2] 正在背景啟動 Web 儀表板 (Port 8000)...
start /b venv\Scripts\python.exe pi\dashboard.py

timeout /t 3 /nobreak > nul

REM 啟動 AI 辨識主程式
echo [2/2] 正在啟動 AI 辨識主程式...
echo ------------------------------------------
echo 提示: 直接關閉此視窗或按 Ctrl+C 可停止。
echo ------------------------------------------
venv\Scripts\python.exe pi\main.py

echo ✅ 系統已結束。
pause
