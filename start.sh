#!/bin/bash
# ==========================================
# 先行一步 (One Step Ahead) - 一鍵啟動腳本
# ==========================================

# 取得腳本所在目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================="
echo "   先行一步 (One Step Ahead) 啟動中..."
echo "=========================================="

# 檢查虛擬環境
if [ ! -d "venv" ]; then
    echo "❌ 錯誤: 找不到 venv 虛擬環境，請先執行 install.sh"
    exit 1
fi

# 啟動整合版主程式 (FastAPI + YOLO)
echo "[1/1] 正在啟動 AI 辨識系統與 Web 儀表板..."
echo "------------------------------------------"
echo "提示: 按 Ctrl+C 可完整停止服務。"
echo "------------------------------------------"

# 貼心功能：自動清理卡住的通訊埠，避免 Address already in use 錯誤
echo "正在清理占用 Port 8000 的舊程序..."
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

venv/bin/python3 pi/app.py

echo "✅ 系統已結束。"
