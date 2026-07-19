import os
import json
import time
import subprocess
import asyncio
import cv2
import httpx
import requests
import socket
import threading
import numpy as np
from collections import deque
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO

from utils import HomographyTransformer, calculate_velocity, is_approaching_curb

# ===================
# CONFIG & INIT
# ===================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"cameras": [], "security": {"api_key": "penny_safety2026"}}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ [CONFIG] 無法讀取設定檔: {e}")
        return {"cameras": [], "security": {"api_key": "penny_safety2026"}}

config = load_config()
API_KEY = config.get("security", {}).get("api_key", "")
is_shutting_down = False

app = FastAPI(title="先行一步 AI 監控儀表板")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Global State
frame_cache = {}
status_cache = {}
discovered_devices = [] # List of {"name": x, "ip": x}
system_logs = deque(maxlen=50)
ai_stats = {}  # {cam_id: {"pedestrians": int, "dangers": int, "nearest_dist": float}}
server_start_time = time.time()
ai_fps_data = {"current": 0.0, "history": deque(maxlen=120)}
alarm_count_today = 0
_last_ai_time = {}

# AI Tracking Config
MODEL_PATH = "yolov8n.pt"
SRC_PTS = [[0, 480], [640, 480], [640, 0], [0, 0]]
DST_PTS = [[0, 5],   [5, 5],     [5, 0],   [0, 0]]
INTENT_THRESHOLD_DIST = 1.2
INTENT_THRESHOLD_VEL  = 0.4
INTENT_MIN_FRAMES     = 4
ALARM_DURATION        = 5
CURB_Y_THRESHOLD      = 2.5

model = None
transformer = None

def add_log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {"time": timestamp, "msg": message, "level": level}
    system_logs.append(entry)
    print(f"[{timestamp}] {level}: {message}")

async def check_tcp_port(host_port: str, default_port: int = 80, timeout: float = 3.0):
    try:
        if ":" in host_port:
            host, port_str = host_port.split(":")
            port = int(port_str)
        else:
            host = host_port
            port = default_port
            
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True, "OPEN"
    except asyncio.TimeoutError:
        return False, "Timeout"
    except ConnectionRefusedError:
        return False, "Refused (Busy)"
    except Exception as e:
        return False, f"Err: {str(e)[:20]}"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

class CameraConfig(BaseModel):
    id: int
    name: str
    ip: str

class SettingsUpdate(BaseModel):
    cameras: List[CameraConfig]

# ===================
# AI TRACKER
# ===================
class PedestrianTracker:
    def __init__(self, cam_ip: str):
        self.cam_ip = cam_ip
        self.tracks = {} 
        self.last_alarm_time = 0
        self._alarm_lock = False

    def _send_alarm_request(self, state):
        try:
            url = f"http://{self.cam_ip}/alarm?state={state}&auth={API_KEY}"
            requests.get(url, timeout=1.5)
        except Exception as e:
            add_log(f"⚠️ [ALARM {self.cam_ip}] 請求發送失敗: {e}", "WARN")
        finally:
            self._alarm_lock = False

    def trigger_alarm(self):
        global alarm_count_today
        now = time.time()
        if self._alarm_lock or (self.last_alarm_time > 0 and now - self.last_alarm_time < ALARM_DURATION):
            return 
            
        add_log(f">>> AI TRIGGER: ACTivating Crosswalk Alarm for {self.cam_ip}", "WARN")
        self._alarm_lock = True
        self.last_alarm_time = now
        alarm_count_today += 1
        threading.Thread(target=self._send_alarm_request, args=("on",), daemon=True).start()

    def reset_alarm_if_needed(self):
        now = time.time()
        if self.last_alarm_time > 0 and now - self.last_alarm_time >= ALARM_DURATION:
            add_log(f">>> AI TRIGGER: DEactivating Crosswalk Alarm for {self.cam_ip}", "INFO")
            self.last_alarm_time = 0
            threading.Thread(target=self._send_alarm_request, args=("off",), daemon=True).start()

    def cleanup_tracks(self):
        now = time.time()
        expired = [tid for tid, info in self.tracks.items() if now - info['last_time'] > 60]
        for tid in expired:
            del self.tracks[tid]
        if expired:
            add_log(f"🧹 [GC] 已清理 {len(expired)} 個過期追蹤 ID ({self.cam_ip})", "DEBUG")

    def update(self, track_id, pos_ground, vehicle_detected):
        now = time.time()
        if track_id not in self.tracks:
            self.tracks[track_id] = {'last_pos': pos_ground, 'last_time': now, 'intent_count': 0}
            return False
        
        info = self.tracks[track_id]
        dt = now - info['last_time']
        if dt <= 0: return False
        
        velocity, vector = calculate_velocity(info['last_pos'], pos_ground, dt)
        approaching, dist = is_approaching_curb(pos_ground, vector, CURB_Y_THRESHOLD)
        
        is_intent = False
        if approaching and dist < INTENT_THRESHOLD_DIST and velocity > INTENT_THRESHOLD_VEL:
            info['intent_count'] += 1
        else:
            info['intent_count'] = max(0, info['intent_count'] - 1)
        
        if info['intent_count'] >= INTENT_MIN_FRAMES:
            # 雙重驗證：行人有意圖穿越 且 感測器偵測到車輛
            if vehicle_detected:
                is_intent = True
                self.trigger_alarm()
            
        info['last_pos'] = pos_ground
        info['last_time'] = now
        return is_intent

# Global instances map
trackers = {}

def detect_pedestrians(frame):
    """
    使用 YOLOv8n + ByteTrack 進行行人偵測與追蹤。
    回傳 list of (track_id, x1, y1, x2, y2)
    """
    global model
    if model is None: return []
    results = model.track(frame, persist=True, classes=[0], tracker="bytetrack.yaml", verbose=False, imgsz=320)
    detections = []
    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        for box, track_id in zip(boxes, ids):
            detections.append((track_id, box[0], box[1], box[2], box[3]))
    return detections

def process_ai_frame(frame, cam_id):
    """同步阻塞的 AI 處理函式：YOLOv8n 偵測 + ByteTrack 追蹤 + Homography 距離計算"""
    global transformer, ai_stats
    
    if cam_id not in trackers:
        cam = next((c for c in config["cameras"] if c["id"] == cam_id), None)
        cam_ip = cam["ip"] if cam else "127.0.0.1"
        trackers[cam_id] = PedestrianTracker(cam_ip)
    
    tracker_logic = trackers[cam_id]
    tracker_logic.reset_alarm_if_needed()
    
    # 定期清理記憶體
    if np.random.rand() < 0.01:
        tracker_logic.cleanup_tracks()
    
    # 取得最新車輛偵測狀態（透過 status_cache）
    vehicle_detected = status_cache.get(cam_id, {}).get("vehicle_detected", False)
    
    # 推論
    detections = detect_pedestrians(frame)
    
    h, w = frame.shape[:2]
    
    # 繪製馬路邊緣參考線 (Curb Line)
    if transformer is not None:
        # 將 curb_y 從地面座標反投影回像素座標作為視覺參考
        curb_pixel_y = int(h * (1.0 - CURB_Y_THRESHOLD / 5.0))  # 近似映射
        cv2.line(frame, (0, curb_pixel_y), (w, curb_pixel_y), (0, 200, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"CURB LINE ({CURB_Y_THRESHOLD:.1f}m)", (10, curb_pixel_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1, cv2.LINE_AA)
    
    # AI 統計計數器
    ped_count = 0
    danger_count = 0
    nearest_dist = 999.0
    
    for track_id, x1, y1, x2, y2 in detections:
        foot_x, foot_y = (x1 + x2) / 2, y2
        gx, gy = transformer.transform(foot_x, foot_y)
        is_danger = tracker_logic.update(track_id, (gx, gy), vehicle_detected)
        
        # 計算距離馬路邊緣的距離
        dist_to_curb = abs(gy - CURB_Y_THRESHOLD)
        
        ped_count += 1
        if is_danger:
            danger_count += 1
        nearest_dist = min(nearest_dist, dist_to_curb)
        
        # ===== 視覺標註 =====
        ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)
        
        if is_danger:
            # 危險：紅色粗框 + 閃爍效果
            color = (0, 0, 255)
            thickness = 2
            # 半透明紅色填充
            overlay = frame.copy()
            cv2.rectangle(overlay, (ix1, iy1), (ix2, iy2), color, -1)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        else:
            # 安全：綠色細框
            color = (0, 255, 0)
            thickness = 1
        
        # Bounding Box
        cv2.rectangle(frame, (ix1, iy1), (ix2, iy2), color, thickness, cv2.LINE_AA)
        
        # 腳部圓點
        cv2.circle(frame, (int(foot_x), int(foot_y)), 5, color, -1, cv2.LINE_AA)
        
        # 距離色彩分級
        if dist_to_curb < 1.0:
            dist_color = (0, 0, 255)    # 紅色 < 1m
        elif dist_to_curb < 2.0:
            dist_color = (0, 200, 255)  # 黃色 1-2m
        else:
            dist_color = (0, 255, 0)    # 綠色 > 2m
        
        # 標籤背景 (提升可讀性)
        label = f"ID:{track_id} {dist_to_curb:.1f}m"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_y = max(iy1 - 8, th + 4)
        cv2.rectangle(frame, (ix1, label_y - th - 4), (ix1 + tw + 6, label_y + 2), (0, 0, 0), -1)
        cv2.putText(frame, label, (ix1 + 3, label_y - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, dist_color, 1, cv2.LINE_AA)
    
    # HUD 資訊疊加 (左上角)
    hud_lines = [
        f"Pedestrians: {ped_count}",
        f"Dangers: {danger_count}",
        f"Nearest: {nearest_dist:.1f}m" if nearest_dist < 900 else "Nearest: --",
    ]
    for i, line in enumerate(hud_lines):
        y_pos = 25 + i * 22
        cv2.putText(frame, line, (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    
    # 更新全域 AI 統計
    ai_stats[cam_id] = {
        "pedestrians": ped_count,
        "dangers": danger_count,
        "nearest_dist": round(nearest_dist, 2) if nearest_dist < 900 else -1,
    }
    
    # 追蹤 AI FPS
    now_t = time.time()
    if cam_id in _last_ai_time:
        dt = now_t - _last_ai_time[cam_id]
        if dt > 0:
            fps = 1.0 / dt
            ai_fps_data["current"] = round(fps, 1)
            ai_fps_data["history"].append({"t": round(now_t, 2), "fps": round(fps, 1)})
    _last_ai_time[cam_id] = now_t
    
    return frame

# ===================
# MDNS DISCOVERY
# ===================
class MDNSListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            addresses = [".".join(map(str, addr)) for addr in info.addresses]
            if addresses:
                ip = addresses[0]
                if "esp32-safety" in name:
                    device = {"name": name.split(".")[0], "ip": ip}
                    if device not in discovered_devices:
                        discovered_devices.append(device)
                        print(f"Discovered via mDNS: {device}")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None: pass
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None: pass

def start_mdns_discovery():
    zeroconf = Zeroconf()
    listener = MDNSListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    return zeroconf

# ===================
# BACKGROUND TASKS
# ===================
async def fetch_camera_data(cam_id: int, ip: str, is_main_camera: bool):
    stream_url = f"http://{ip}/stream?auth={API_KEY}"
    status_url = f"http://{ip}/status?auth={API_KEY}"
    
    async def poll_status():
        async with httpx.AsyncClient() as client:
            while not is_shutting_down:
                start_time = asyncio.get_event_loop().time()
                try:
                    resp = await client.get(status_url, timeout=3.0)
                    latency = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    if resp.status_code == 200:
                        data = resp.json()
                        data["latency"] = latency
                        data["tcp"] = "OPEN"
                        status_cache[cam_id] = data
                    else:
                        add_log(f"🔥 [CAM {cam_id}] 認證失敗: HTTP {resp.status_code}", "ERROR")
                        status_cache[cam_id] = {"error": f"HTTP {resp.status_code}", "tcp": "OPEN"}
                except Exception:
                    status_cache[cam_id] = {"error": "Timeout", "tcp": "CLOSED"}
                await asyncio.sleep(1)

    async def poll_video():
        reconnect_delay = 5
        while not is_shutting_down:
            try:
                is_port_open, msg = await check_tcp_port(ip, 80)
                if not is_port_open:
                    add_log(f"⚠️ [CAM {cam_id}] TCP 連線異常 ({msg})", "WARN")
                    await asyncio.sleep(min(reconnect_delay, 60))
                    reconnect_delay *= 2
                    continue
                
                reconnect_delay = 5
                
                async with httpx.AsyncClient() as client:
                    async with client.stream("GET", stream_url, timeout=10.0) as response:
                        if response.status_code != 200:
                            if response.status_code == 401:
                                add_log(f"🔥 [CAM {cam_id}] 認證失敗 (API Key 錯誤)", "ERROR")
                            else:
                                add_log(f"⚠️ [CAM {cam_id}] 影像流回應異常 (HTTP {response.status_code})", "WARN")
                            await asyncio.sleep(10)
                            continue
                        
                        add_log(f"✅ [CAM {cam_id}] 串流建立成功", "INFO")
                        
                        buffer = b""
                        async for chunk in response.aiter_bytes():
                            if is_shutting_down: break
                            buffer += chunk
                            
                            latest_jpg = None
                            while True:
                                a = buffer.find(b'\xff\xd8')
                                if a == -1:
                                    # 找不到起點，保留最後一個 byte 避免切斷標籤
                                    buffer = buffer[-1:]
                                    break
                                b = buffer.find(b'\xff\xd9', a)
                                if b == -1:
                                    # 有起點但還沒收到終點，把前面的垃圾資料丟掉，等待下一個 chunk
                                    buffer = buffer[a:]
                                    break
                                
                                # 完整收到一張照片
                                latest_jpg = buffer[a:b+2]
                                buffer = buffer[b+2:]
                                    
                            if latest_jpg is not None:
                                # 光速存入快取，讓前端可以 0 延遲拿到原始影像
                                frame_cache[cam_id] = latest_jpg
                                
                                # 如果有載入 AI，丟給背景處理，不阻塞網路讀取！
                                if is_main_camera and model is not None:
                                    if not getattr(loop, "ai_busy", False):
                                        loop.ai_busy = True
                                        async def ai_bg_task(raw_jpg, cid):
                                            try:
                                                f = await loop.run_in_executor(None, lambda: cv2.imdecode(np.frombuffer(raw_jpg, np.uint8), cv2.IMREAD_COLOR))
                                                if f is not None:
                                                    # YOLO 需要固定解析度
                                                    h, w = f.shape[:2]
                                                    if w != 640 or h != 480:
                                                        f = await loop.run_in_executor(None, lambda: cv2.resize(f, (640, 480)))
                                                    res_f = await loop.run_in_executor(None, process_ai_frame, f, cid)
                                                    s, b_jpg = await loop.run_in_executor(None, lambda: cv2.imencode('.jpg', res_f, [cv2.IMWRITE_JPEG_QUALITY, 80]))
                                                    if s: 
                                                        # AI 處理完後覆蓋快取
                                                        frame_cache[cid] = b_jpg.tobytes()
                                            finally:
                                                loop.ai_busy = False
                                        asyncio.create_task(ai_bg_task(latest_jpg, cam_id))
                                    
                            # 把 buffer 限制改小一點，避免塞爆記憶體或讀到過舊的影像資料
                            if len(buffer) > 200000:
                                buffer = b""
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                add_log(f"🔥 [CAM {cam_id}] 串流中斷: {str(e)[:30]}", "ERROR")
                await asyncio.sleep(5)
    
    await asyncio.gather(poll_status(), poll_video())

active_tasks = []
zc_instance = None

def start_all_fetchers():
    global active_tasks
    for task in active_tasks: task.cancel()
    active_tasks = []
    # 假設預設第一台為需要 AI 分析的主攝影機
    main_cam_id = config["cameras"][0]["id"] if config["cameras"] else None
    for cam in config["cameras"]:
        is_main = (cam["id"] == main_cam_id)
        task = asyncio.create_task(fetch_camera_data(cam["id"], cam["ip"], is_main))
        active_tasks.append(task)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global zc_instance, is_shutting_down, model, transformer
    add_log("🚀 正在載入 YOLOv8n 模型與初始化 Homography Transformer...", "INFO")
    try:
        model = YOLO(MODEL_PATH)
        transformer = HomographyTransformer(SRC_PTS, DST_PTS)
        add_log("✅ AI 推論引擎已啟用 (YOLOv8n + ByteTrack + Homography)", "INFO")
    except Exception as e:
        model = None
        transformer = None
        add_log(f"⚠️ AI 模型載入失敗，系統以純串流模式運行: {e}", "WARN")
    
    start_all_fetchers()
    zc_instance = start_mdns_discovery()
    yield
    
    is_shutting_down = True
    add_log("🛑 系統正在關閉背景任務...", "WARN")
    if zc_instance: zc_instance.close()
    for task in active_tasks: task.cancel()
    if active_tasks:
        await asyncio.gather(*active_tasks, return_exceptions=True)
    print("✅ 資源已釋放。")

app = FastAPI(title="One Step Ahead Dashboard", lifespan=lifespan)

# ===================
# ENDPOINTS
# ===================

@app.get("/favicon.ico")
async def favicon():
    return StreamingResponse(iter([]), status_code=204)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"cameras": config["cameras"], "API_KEY": API_KEY}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="settings.html",
        context={"cameras": config["cameras"]}
    )

@app.post("/settings")
async def update_settings(data: SettingsUpdate):
    global config
    config["cameras"] = [cam.model_dump() for cam in data.cameras]
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    start_all_fetchers()
    return {"status": "ok"}

@app.get("/scan")
async def scan_devices():
    return discovered_devices

@app.post("/control/{cam_id}/{state}")
async def control_led(cam_id: int, state: str):
    cam = next((c for c in config["cameras"] if c["id"] == cam_id), None)
    if not cam: return {"status": "error"}
    target_url = f"http://{cam['ip']}/alarm?state={state}&auth={API_KEY}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(target_url, timeout=2.0)
            return {"status": "ok"}
        except: return {"status": "error"}

async def gen_frames(cam_id: int):
    while not is_shutting_down:
        if cam_id in frame_cache:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_cache[cam_id] + b'\r\n')
        await asyncio.sleep(1/20)

@app.get("/video_feed/{cam_id}")
async def video_feed(cam_id: int):
    return StreamingResponse(gen_frames(cam_id), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/logs")
async def get_logs():
    return list(system_logs)

@app.get("/api/net_info")
async def get_net_info():
    return {"local_ip": get_local_ip(), "hostname": socket.gethostname()}

@app.get("/api/wifi_status")
async def get_wifi_status():
    if os.name == 'nt':
        return {"mode": "Simulation", "ssid": "OneStepAhead_AP (MOCK)", "clients": 0}
    try:
        res = subprocess.check_output(["nmcli", "-t", "-f", "ACTIVE,SSID,MODE", "dev", "wifi"], text=True, stderr=subprocess.DEVNULL)
        for line in res.splitlines():
            if line.startswith("yes"):
                parts = line.split(":")
                return {"mode": parts[2], "ssid": parts[1], "clients": "N/A"}
        return {"mode": "Disconnected", "ssid": "None", "clients": 0}
    except:
        return {"mode": "Unknown", "ssid": "None", "clients": 0}

@app.get("/api/ping/{target}")
async def ping_target(target: str):
    success, msg = await check_tcp_port(target, 80, timeout=3.0)
    return {"status": "success" if success else "failed", "message": msg, "target": target}

@app.post("/api/restart")
async def restart_fetchers():
    add_log("🔄 系統正在重啟所有攝影機連線任務...")
    start_all_fetchers()
    return {"status": "restarting"}

@app.get("/status")
async def get_status():
    combined_status = []
    for cam in config["cameras"]:
        cam_id = cam["id"]
        online = cam_id in frame_cache
        data = status_cache.get(cam_id, {"rssi": 0, "uptime": 0, "sensor": 0.0, "alarm": 0, "tcp": "UNKNOWN", "latency": -1})
        combined_status.append({
            "id": cam_id, "ip": cam["ip"],
            "online": online, "rssi": data.get("rssi", 0), 
            "uptime": data.get("uptime", 0),
            "sensor": data.get("sensor", 0.0), 
            "alarm": data.get("alarm", 0),
            "tcp": data.get("tcp", "UNKNOWN"),
            "latency": data.get("latency", -1)
        })
    return combined_status

@app.get("/api/ai_stats")
async def get_ai_stats():
    """回傳各攝影機的 AI 偵測即時統計"""
    return {
        "model_loaded": model is not None,
        "cameras": ai_stats,
    }

@app.get("/api/system_resources")
async def get_system_resources():
    """回傳系統資源使用狀況 (CPU, RAM, 溫度)"""
    data = {"cpu": 0, "ram": 0, "temp": 0}
    try:
        import psutil
        data["cpu"] = psutil.cpu_percent(interval=0)
        data["ram"] = psutil.virtual_memory().percent
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for entries in temps.values():
                    if entries:
                        data["temp"] = round(entries[0].current, 1)
                        break
        except (AttributeError, Exception):
            pass
    except ImportError:
        pass
    return data

@app.get("/api/dashboard_summary")
async def get_dashboard_summary():
    """回傳儀表板摘要 (頂部列統計)"""
    cams = config.get("cameras", [])
    total = len(cams)
    connected = sum(1 for c in cams if c["id"] in frame_cache)
    avg_lat = 0
    lat_count = 0
    for c in cams:
        lat = status_cache.get(c["id"], {}).get("latency", -1)
        if lat >= 0:
            avg_lat += lat
            lat_count += 1
    if lat_count > 0:
        avg_lat = int(avg_lat / lat_count)
    uptime = int(time.time() - server_start_time)
    return {
        "connected": connected,
        "total": total,
        "ai_fps": ai_fps_data["current"],
        "alarm_count_today": alarm_count_today,
        "avg_latency": avg_lat,
        "uptime": uptime,
    }

@app.get("/api/ai_fps_history")
async def get_ai_fps_history():
    """回傳 AI FPS 歷史數據 (圖表用)"""
    return list(ai_fps_data["history"])

if __name__ == "__main__":
    import os
    import uvicorn
    import signal

    port = config.get("server", {}).get("port", 8000)
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", timeout_graceful_shutdown=1)
    server = uvicorn.Server(uv_config)

    shutdown_calls = 0
    def handle_exit(sig, frame):
        global shutdown_calls, is_shutting_down
        shutdown_calls += 1
        is_shutting_down = True
        if shutdown_calls > 1:
            print("\n[FORCE] 強制退出進程...")
            os._exit(1)
        print("\n\n[INFO] 正在關閉系統資源 (再按一次 Ctrl+C 可強制退出)...")
        asyncio.create_task(server.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_exit)

    try:
        asyncio.run(server.serve())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        os._exit(0)
