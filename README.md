# 先行一步 (One Step Ahead)：邊緣運算 AI 交通監控系統

本專案致力於透過邊緣運算 (Edge AI) 技術提升路口行人安全。透過即時影像辨識行人動態，並在必要時觸發邊緣端的 LED 警示看板，主動降低人車衝突風險。

> **專案背景**
> * **參與競賽**：115年人本環境全國大專院校學生競賽
> * **隊伍名稱**：前方來車請注意


---

## 🌟 系統亮點與核心功能

* **AI 即時精準偵測**：採用 YOLOv8n 搭配 ByteTrack 物件追蹤，並結合 Homography 投影技術，精準計算行人與路口危險區域的實際距離。
* **分散式邊緣運算**：以 Raspberry Pi 5 作為中樞管理站，並行處理多台 ESP32-CAM 邊緣影像採集節點的串流數據。
* **毫秒級自動化警示**：當行人進入預設危險區域，系統將以非同步協程技術，遠端觸發 ESP32 上的 LED 警示燈，整體影像與控制延遲控制在 300ms 以下。
* **現代化 Web 管理儀表板**：內建基於 FastAPI 的控制中心，支援即時影像看版、系統參數熱更新與網路連線診斷。

### 🛠️ 技術棧 (Tech Stack)

| 領域 | 使用技術 |
| --- | --- |
| **AI 視覺** | YOLOv8 (Ultralytics), ByteTrack, OpenCV, Homography (透視變換) |
| **後端與 API** | Python 3.11+, FastAPI, Uvicorn, Zeroconf (mDNS 自動發現) |
| **邊緣硬體** | C++, Arduino ESP32 Core, mDNS Responder |
| **前端儀表板** | HTML5, CSS3 (Glassmorphism), JavaScript (Async Fetch), Jinja2 |

---

## 📋 硬體建置指南

### 1. 零件清單 (BOM)

* **中樞大腦**：Raspberry Pi 5 (8GB RAM，建議搭配散熱風扇)
* **邊緣節點**：AI-Thinker ESP32-CAM 模組
* **感測與警示**：霍爾感測器 (磁場偵測)、單路繼電器模組、5V/12V LED 警示燈條
* **其他**：高度 3.5m - 5m 之固定支架/外殼

### 2. ESP32-CAM 接線定義

請將 ESP32-CAM **背面（印有白字面）朝上**，依照以下腳位連接：

* **霍爾感測器 (偵測車輛靠近)**：`VCC` ➔ `3V3` ｜ `GND` ➔ `GND` ｜ `DO` ➔ **`GPIO 14`**
* **繼電器模組 (控制警示燈)**：`VCC` ➔ `5V` ｜ `GND` ➔ `GND` ｜ `IN (S)` ➔ **`GPIO 12`**

> **💡 獨家大補帖：雙線路穩定供電與燒錄大法**
> 針對 ESP32-CAM 在啟動 Wi-Fi 時常發生的 `Brownout` (供電不足導致無限重啟) 問題，本專案強烈建議採用「雙 UART 共地法」：
> 1. **供電端 (UART A)**：連接手機充電頭，`5V` 與 `GND` 接入麵包板提供純淨大電流。
> 2. **通訊端 (UART B)**：連接電腦 USB，負責 `TX`、`RX` 傳輸，其 `GND` 必須與供電端**共地**。*(⚠️ 絕對禁止將通訊端的 5V 接入 ESP32)*
> 3. **燒錄控制**：將 `IO0` 接地並按 `RST` 進入燒錄模式；燒錄完成後將 `IO0` 懸空並按 `RST`，即可在電腦序列埠穩定監看執行日誌。
> 
> 

---

## 🚀 軟體部署與快速開始

### Raspberry Pi 5 部署

**Step 1: 環境自動化安裝 (首次執行)**

```bash
curl -sSL https://raw.githubusercontent.com/sungpenny93-creator/pedestrian-safety/main/install.sh | bash

```

**Step 2: 啟動行動部署模式 (建立私有網段)**
為確保戶外展示的穩定性，將 Pi 設為專屬 Wi-Fi 熱點供邊緣節點連線：

```bash
cd pedestrian-safety
sudo bash pi/setup_ap.sh

```

*(熱點名稱：`OneStepAhead_AP` ｜ 預設密碼：`PennySafety@2026` ｜ 預設 IP：`192.168.4.1`)*

**Step 3: 一鍵啟動 AI 與儀表板**
確認 ESP32-CAM 已通電並連上熱點後，執行啟動腳本：

```bash
bash start.sh

```

啟動後，請使用設備連線至熱點，並開啟瀏覽器訪問 👉 **`http://192.168.4.1:8000`**


## 🔒 系統安全與疑難排解

### 安全性防護 (Security)

1. **API 認證機制**：後端對 ESP32-CAM 的所有 HTTP 請求 (如 `/stream`, `/alarm`) 皆需攜帶 `auth` 參數驗證。
2. **跨網域保護**：FastAPI 後端已實作 CORS 限制，僅允許授權來源訪問控制端點。

### 常見網路問題排除 (Troubleshooting)

* **無法獲取影像串流？**
* 檢查 `OneStepAhead_AP` 熱點是否正常運作。
* 前往儀表板的「系統設定」，使用「連線測試 (TCP)」功能 Ping 測試攝影機 IP。