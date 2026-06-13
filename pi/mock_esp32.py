import cv2
import time
import asyncio
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI(title="Mock ESP32-CAM Simulator")

# State
alarm_active = 0
start_time = time.time()

# Create a placeholder image
def create_placeholder():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "MOCK ESP32 STREAM", (150, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return img

@app.get("/status")
async def get_status():
    uptime = int(time.time() - start_time)
    # Simulate some fluctuating sensor data and RSSI 
    rssi = -50 - (uptime % 10) 
    sensor = 1.2 + (uptime % 5) * 0.1
    return {
        "rssi": rssi,
        "uptime": uptime,
        "sensor": sensor,
        "alarm": alarm_active
    }

@app.get("/alarm")
async def set_alarm(state: str):
    global alarm_active
    if state == "on":
        alarm_active = 1
        print(">>> [MOCK ESP32] ALARM ON: Crosswalk LED Lit!")
    else:
        alarm_active = 0
        print(">>> [MOCK ESP32] ALARM OFF: Crosswalk LED Dark.")
    return "OK"

async def gen_frames():
    while True:
        # Create a frame with a moving "pedestrian" box
        img = create_placeholder()
        t = time.time()
        bx = int(320 + 200 * np.sin(t))
        by = int(240 + 100 * np.cos(t))
        cv2.rectangle(img, (bx-20, by-50), (bx+20, by), (0, 255, 0), 2)
        cv2.putText(img, "SIMULATED PEDESTRIAN", (bx-50, by-60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        if alarm_active:
            cv2.circle(img, (50, 50), 20, (0, 165, 255), -1) # Amber alert icon
            cv2.putText(img, "ALARM ACTIVE", (80, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        _, buffer = cv2.imencode('.jpg', img)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        await asyncio.sleep(0.1)

@app.get("/stream")
async def stream():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    print("Starting Mock ESP32 Simulator on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
