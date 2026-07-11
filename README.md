# 先行一步 (One Step Ahead)：邊緣運算 AI 交通監控系統

[![Competition](https://img.shields.io/badge/Competition-115%E5%B9%B4%E4%BA%BA%E6%9C%AC%E7%92%B0%E5%A2%83%E5%85%A8%E5%9C%8B%E5%A4%A7%E5%B0%88%E9%99%A2%E6%A0%A1%E5%AD%B8%E7%94%9F%E7%AB%B6%E8%B3%BD-FFB300.svg)](https://example.com)
[![Status](https://img.shields.io/badge/Status-Prototype_Ready-green.svg)]()
[![Platform](https://img.shields.io/badge/Platform-Raspberry_Pi_5-C51A4A.svg)]()

本專案致力於透過邊緣運算 (Edge AI) 技術提升路口行人安全。透過即時影像辨識行人動態，並在必要時觸發邊緣端的 LED 警示看板，降低人車衝突風險。

---

## 🌟 核心功能
- **AI 即時偵測**：使用 YOLOv8n + ByteTrack，結合 Homography 投影技術精準計算行人與路口的距離。
- **邊緣端串流技術**：Raspberry Pi 5 作為核心處理站，同時管理多台 ESP32-CAM 影像採集節點。
- **自動化警示**：辨識到行人進入危險區域時，自動遠端觸發 ESP32 上的 LED 警示燈。
- **現代化管理介面**：基於 FastAPI 的 Web Dashboard，支援即時影像看版、參數設定與網路連線診斷。
- **低延遲優化**：採用非同步協程與多執行緒處理，確保影像延遲保持在 300ms 以下。

---

## 🛠️ 技術棧 (Technological Stack)
| 領域 | 使用技術 |
| :--- | :--- |
| **AI & 影像辨識** | YOLOv8 (Ultralytics), ByteTrack (追蹤), OpenCV, Homography (透視變換) |
| **後端架構** | Python 3.11+, FastAPI, Uvicorn, Zeroconf (mDNS 自動發現) |
| **嵌入式開發** | C++, Arduino ESP32 Core, esp_http_server, mDNS Responder |
| **前端介面** | HTML5, CSS3 (Glassmorphism), JavaScript (Async Fetch), Jinja2 |
| **部署環境** | Linux Bash Shell, Python Virtual Environment (venv) |

---

## 📋 零件清單 (Bill of Materials)
| 硬體名稱 | 角色 | 建議規格 |
| :--- | :--- | :--- |
| **Raspberry Pi 5** | 核心運算與管理站 | 8GB RAM, 建議搭配散熱風扇 |
| **ESP32-CAM** | 邊緣影像與 LED 控制站 | AI-Thinker 模組 |
| **LED 警示模組** | 行人警示顯示 | 5V/12V LED Strip (接 **GPIO 12**) |
| **外殼/支架** | 硬體防護與固定 | 建議高度 3.5m - 5m |

---

## 🚀 快速開始 (Quick Start)

### A. Raspberry Pi 端 (處理中心)

**【第一步：自動化環境安裝】** (僅首次建置需要)
打開 Raspberry Pi 終端機，執行一鍵下載與安裝指令：
```bash
curl -sSL https://raw.githubusercontent.com/sungpenny93-creator/pedestrian-safety/main/install.sh | bash
```

**【第二步：開啟 Wi-Fi 基地台】** (每次開機或展示前)
為了讓 ESP32 攝影機能夠連線，並讓您的手機/筆電能觀看畫面，請將樹莓派切換為熱點模式：
```bash
cd pedestrian-safety
sudo bash pi/setup_ap.sh
```
*(執行後，樹莓派會發射名為 `OneStepAhead_AP` 的 Wi-Fi 訊號，密碼：PennySafety@2026)*

**【第三步：啟動 AI 與儀表板】**
確認 ESP32 已經通電後，執行一鍵啟動腳本：
```bash
bash start.sh
```
*(系統會自動清理佔用的 Port，並啟動 YOLO 辨識與 FastAPI 儀表板)*

**【第四步：觀看成果畫面】**
用手機或筆電連上 `OneStepAhead_AP` 的 Wi-Fi，打開瀏覽器訪問：
👉 **`http://192.168.4.1:8000`**

### B. ESP32-CAM 端 (硬體與採集端)

#### 1. 硬體接線指南 (Pinout Wiring)
請將 ESP32-CAM **背面（印有白字面）朝上**，依照以下位置使用杜邦線連接：

**🧲 霍爾感測器 (車輛偵測)**
- `VCC` (電源) ➡️ ESP32 右上角的 **`3V3`**
- `GND` (接地) ➡️ ESP32 右邊中間的 **`GND`**
- `DO` (訊號) ➡️ ESP32 左下角的 **`14`** (對應 GPIO 14)

**💡 繼電器模組 (控制警示燈)**
*(模組上標示可能為 VCC/GND/IN 或 +/-/S)*
- `VCC` 或 `+` (電源) ➡️ ESP32 左上角的 **`5V`**
- `GND` 或 `-` (接地) ➡️ ESP32 左邊數來第二根 **`GND`**
- `IN` 或 `S` (訊號) ➡️ ESP32 左邊數來第三根 **`12`** (對應 GPIO 12)

#### 2. 軟體燒錄
1. 使用 Arduino IDE 開啟 `esp32/camera_stream/camera_stream.ino`。
2. 開發板選擇 **AI Thinker ESP32-CAM** 並燒錄。
8. (選用) 程式內已內建「硬體即時測試模式」，通電後只要拿磁鐵靠近霍爾感測器，繼電器就會立刻觸發。

#### 3. 雙線路穩定供電與燒錄大法 (解決不斷重啟/Brownout)
如果您在燒錄或連線時遇到 ESP32 不斷重啟，請使用「雙 UART 模組共地法」徹底解決供電問題：

**1. 基礎建設：建立「共地」軌道**
這一步最重要！請把麵包板最下方的藍色 `-` 軌道當作大家的「GND 總站」。

**2. UART A（力量擔當：負責供電）**
這塊板子插在蘋果豆腐頭 / 牆壁插座上，只提供純淨強大的電流。
- `5V` ➜ 接到 ESP32-CAM 的 `5V` 腳位。
- `GND` ➜ 接到麵包板的 藍色 `-` GND 總站。
*(其他 TX, RX 全部空著不要接)*

**3. UART B（大腦擔當：負責燒錄與監控）**
這塊板子插在您的電腦 USB 上，負責讓 Arduino IDE 傳輸程式碼和監看文字。
- `TX` ➜ 接到 ESP32-CAM 的 `U0R` (這根是 RX)。
- `RX` ➜ 接到 ESP32-CAM 的 `U0T` (這根是 TX)。
- `GND` ➜ 接到麵包板的 藍色 `-` GND 總站。（這就是共地！）

> [!WARNING]
> 絕對禁止：UART B 的 5V 或 3V3 千萬不要接到 ESP32！因為 ESP32 已經在吃 UART A 的電了，如果兩邊同時給電，電壓衝突會把板子燒毀。

**4. ESP32-CAM（燒錄控制線）**
- `IO0` ➜ 準備一條杜邦線插在 IO0 上，另一端懸空拿在手上備用。

**🎮 操作 SOP**
線路整理好之後，未來的操作會變得非常優雅明確：

*   **【模式一：我要燒錄新程式】**
    1. 把 ESP32 的 `IO0` 接到 藍色 `-` GND 總站。
    2. 按下 ESP32 板子背面的 RST (Reset) 按鈕一次（或是把 5V 電源拔掉重插）。
    3. 在電腦 Arduino IDE 點擊「上傳」。
    4. 等待畫面顯示燒錄 100% 完成。
*   **【模式二：我要讓它自己跑，並在電腦看監控】**
    1. 把 `IO0` 從 GND 總站拔掉（讓它懸空）。
    2. 按下 ESP32 板子背面的 RST (Reset) 按鈕一次（或是把 5V 電源拔掉重插）。
    3. 打開 Arduino IDE 的「序列埠監控視窗」。
    4. 這時候因為有豆腐頭穩定的供電，它就不會再無限重啟，您可以舒舒服服地在電腦上看它連上 Wi-Fi 的成功訊息了！

---

## ⚡ 一鍵啟動 (One-Click Start)

為了方便現場演示，您可以直接執行以下腳本同時啟動 AI 辨識與管理介面：

- **Linux / Raspberry Pi**:
  ```bash
  chmod +x start.sh
  ./start.sh
  ```
- **Windows**: 直接雙擊執行 `start.bat` 即可。

---

## 🏕️ 行動部署模式 (Portable AP Mode)

為了在沒有路由器的環境下進行展示，本系統支援將 Raspberry Pi 設為 Wi-Fi 基地台：

1. **執行設定腳本**:
   ```bash
   sudo chmod +x pi/setup_ap.sh
   sudo ./pi/setup_ap.sh
   ```
2. **預設熱點資訊**:
   - **SSID**: OneStepAhead_AP
   - **Password**: PennySafety@2026
   - **Pi IP**: 192.168.4.1
3. **儀表板監控**: 啟動後，首頁將出現「Pi 基地台狀態」卡片，顯示當前熱點名稱與連線狀態。

---

## 🧪 模擬與測試 (Windows/Judge Testing)
如果您在沒有實體硬體的情況下想要預覽功能：
1. **環境配置**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r pi/requirements.txt
   ```
2. **啟動模擬器**: `python pi/mock_esp32.py`
3. **啟動系統**: `python pi/app.py`
4. 訪問 http://localhost:8000 即可看到虛擬測試畫面與網路診斷數據。

---

## 📂 專案結構
```text
├── docs/             # 專案文件與設計說明
├── esp32/            # ESP32-CAM 韌體源碼 (C++)
├── pi/
│   ├── templates/    # Web 管理介面 UI (HTML/CSS)
│   ├── app.py        # 整合版主程式 (AI 辨識 + FastAPI 儀表板)
│   ├── main.py       # (舊版保留) 獨立 AI 辨識模組
│   ├── dashboard.py  # (舊版保留) 獨立 FastAPI 後端
│   ├── mock_esp32.py # 軟體模擬器
│   └── utils.py      # 通用工具函式
├── install.sh        # 環境安裝腳本 (Linux)
├── start.sh          # 一鍵啟動腳本 (Linux/Pi)
├── start.bat         # 一鍵啟動腳本 (Windows)
└── README.md         # 專案說明文件
```

---

## 🎓 專案背景：本作品參加 **115年人本環境全國大專院校學生競賽**
- **隊伍名稱**: nono-pi-4g
- **參賽 ID**: 50915133
- **開發時間**: 2026年4月

---

## 🔒 安全性說明 (Security)

本專案已實作基本的資安防護機制：

1. **隱私保護**：Wi-Fi 與 API 金鑰存放在 `esp32/secrets.h`，已加入 `.gitignore`，請勿上傳至公開倉庫。
2. **API 認證**：所有對 ESP32-CAM 的 HTTP 請求必須攜帶 `auth` 參數，範例：`http://{IP}/stream?auth={KEY}`
3. **金鑰同步**：若要更改金鑰，請同時修改 `esp32/secrets.h` 與 `pi/config.json` 中的 `api_key` 欄位。
4. **CORS 安全**：後端已限制僅允許特定來源訪問。若需遠端管理，建議搭配 VPN 或 SSH Tunnel。

---

## 🌐 網路排錯指南 (Network Troubleshooting)

若影像無法顯示，請檢查以下幾點：

1. **檢查網段是否一致**：確保 Pi 與 ESP32-CAM 在同一個 Wi-Fi 下，IP 網段相同。
2. **使用連線測試工具**：在「系統設定」頁中使用「連線測試 (TCP)」功能測試攝影機 IP。
3. **mDNS 自動發現**：確保路由器沒有阻擋 mDNS 封包（設備名稱通常為 esp32-safety）。
4. **硬體隔離 (AP Isolation)**：部分路由器的無線隔離功能會導致 Pi 無法連線 ESP32，請關閉此功能。
5. **模擬器測試**：可先執行 `python pi/mock_esp32.py` 並新增 `127.0.0.1:8080` 作為攝影機進行測試。
