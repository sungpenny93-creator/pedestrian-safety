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

# 啟動 Web 儀表板 (背景執行)
echo "[1/2] 正在啟動 Web 儀表板 (Port 8000)..."
venv/bin/python3 pi/dashboard.py &
DASHBOARD_PID=$!

# 等待一下確保後端啟動
sleep 3

# 啟動 AI 辨識主程式 (前景執行，以便觀察 YOLO 日誌)
echo "[2/2] 正在啟動 AI 辨識主程式..."
echo "------------------------------------------"
echo "提示: 按 Ctrl+C 兩次可完整停止所有程式。"
echo "------------------------------------------"
venv/bin/python3 pi/main.py

# 當 AI 結束時，也關掉背景的儀表板
echo "🛑 正在關閉背景服務..."
kill $DASHBOARD_PID 2>/dev/null
wait $DASHBOARD_PID 2>/dev/null

echo "✅ 所有系統已結束。"
