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

---

## 👨‍💻 專案技術深度解析與實作分享 (硬體與系統部署篇)

本區塊由負責**硬體建置**、**樹莓派系統快速部署**及**儀表板伺服器架設**的團隊成員撰寫，統整了在實際落地過程中所使用的關鍵技術與問題解決方案。

### 1. 樹莓派自動化快速部署技術
為了讓專案能夠在沒有網路或乾淨的 Raspberry Pi 5 環境中一鍵啟動，我開發了全自動化的 Shell Scripts (`install.sh`, `setup_ap.sh`, `start.sh`)，運用了以下技術與策略：

* **Bash Scripting 系統自動化**：
  * 利用 Shell Script 自動安裝系統級依賴 (`apt-get`)，如 `liblgpio-dev` 與 `opencv` 函式庫。
  * 自動化建立 Python 虛擬環境 (`venv`) 並隔離全域套件，確保執行環境乾淨穩定。
* **Python 套件編碼與依賴問題排除 (Problem Solving)**：
  * **問題**：在較新的 Python 3.11+ 版本中，`pip` 解析某些套件 (如 scipy) 的 `METADATA` 時會遇到 `UnicodeDecodeError` 導致安裝中斷。
  * **解決**：在 `install.sh` 中撰寫了一段 Python 腳本 `fix_metadata_encoding()`，自動遞迴掃描並強制將 `METADATA` 轉碼為 `UTF-8`，徹底解決相依性解析失敗的問題。
* **儲存空間與效能最佳化**：
  * 強制透過指定 `--index-url` 安裝 **CPU-Only 版本** 的 PyTorch (`torch`, `torchvision`)。這不僅省下了高達 1.5GB 的磁碟空間 (排除了無用的 NVIDIA CUDA 庫)，也大幅加快了部署速度。
  * 在部署腳本結尾加入自動下載 YOLOv8n 預訓練模型 (`yolov8n.pt`) 的指令，避免系統第一次啟動時因下載模型而造成畫面卡頓。
* **通訊埠衝突自動清理**：
  * 在 `start.sh` 中整合了 `fuser -k 8000/tcp`，解決了伺服器非正常關閉後導致的 `Address already in use` 錯誤，實現真正的一鍵重啟。

### 2. 獨立網段建置與連線穩定度優化
由於系統需要在戶外無網路的環境下展示，我利用 Raspberry Pi 建立了專屬的 Wi-Fi 基礎設施。

* **NetworkManager (`nmcli`) 進階設定**：
  * 透過 `setup_ap.sh` 將 Pi 5 網卡 (`wlan0`) 設置為 Access Point 模式，並建立 `192.168.4.1` 的獨立網段。
* **解決 ESP32 連線不穩問題 (Problem Solving)**：
  * **問題**：ESP32-CAM 在連接現代 Wi-Fi 路由器時，常發生連線頻繁中斷或無法獲取 IP 的問題。
  * **解決**：深入研究後，我透過 `nmcli` 強制套用最嚴格的相容性設定：
    1. 鎖定為 **2.4GHz 頻段** (802.11 b/g) 與頻道 1。
    2. 強制使用 WPA2 (RSN) 與 AES (CCMP) 加密，關閉 WPA3 混淆。
    3. 關閉 PMF (Protected Management Frames，`wifi-sec.pmf 1`)。
    4. **關閉 Wi-Fi 休眠省電模式** (`802-11-wireless.powersave 2`)，確保熱點不間斷廣播。

### 3. ESP32-CAM 硬體韌體與電源管理
在邊緣節點的實作上，我除了負責腳位接線，也處理了底層硬體的穩定性問題。

* **C++ 與 Arduino Core for ESP32**：使用 C++ 撰寫韌體，整合 `esp_camera.h` 與 `esp_http_server.h` 建立 MJPEG 影像串流伺服器。
* **硬體層級的錯誤恢復機制**：
  * **問題**：相機感光元件 (OV2640) 偶爾會因 DMA 緩衝區溢出而當機。
  * **解決**：在韌體中加入了 Watchdog 機制，當 `esp_camera_fb_get()` 拿不到影像時，系統會自動呼叫 `ESP.restart()` 重啟恢復。同時將 `fb_count` 嚴格設定為 2，並在串流迴圈中加入 `delay(30)` 釋放 CPU 資源給 FreeRTOS 處理 Wi-Fi 任務。
* **雙 UART 共地供電法 (Brownout 解決方案)**：
  * 解決了 ESP32-CAM 惡名昭彰的啟動掉壓 (Brownout Detector was triggered) 問題。透過將供電端 (5V大電流) 與通訊端 (序列埠) 分離但共地，確保了相機啟動瞬間瞬間大電流不會拉垮電壓。

### 4. 儀表板伺服器架設與微服務協定
雖然我不負責前端 UI 與 AI 辨識演算法，但我負責將其架設為可執行的伺服器環境。

* **FastAPI 與 Uvicorn 異步伺服器**：
  * 架設基於 ASGI 的非同步 Web 伺服器，負責處理 HTTP 請求並透過 MJPEG (`multipart/x-mixed-replace`) 將 AI 辨識後的影像回傳給瀏覽器。
* **mDNS (Multicast DNS) 區域網路自動發現**：
  * 為了避免每次都要手動輸入 ESP32 的 IP 位址，我在系統中整合了 `Zeroconf` (Python) 與 `ESPmDNS` (C++)。
  * 只要 ESP32 開機，便會廣播 `esp32-safety.local`，儀表板後端會自動攔截並列出可用設備，大幅降低了現場部署的難度。
* **多執行緒與併發處理**：
  * 架構上確保了 AI 推論 (耗時運算)、影像串流擷取 (I/O) 與網頁伺服器回應分別在不同的執行緒或非同步 Task 中運行，確保儀表板網頁不會因為 AI 運算而卡死。