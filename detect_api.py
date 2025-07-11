import cv2
import requests
from datetime import datetime
import os
from ultralytics import YOLO
import json
import time
import threading

# ========== CONFIG ==========
CAM_CONFIG_FILE = 'camera_config.json'
SERVER_URL = 'http://127.0.0.1:5000/upload_log'  # Replace with your Render/PC IP if needed
DETECTION_STATE_FILE = 'detection_state.json'
SCREENSHOT_FOLDER = 'screenshots'
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# ========== Load YOLOv8 ==========
model = YOLO('yolov8n.pt')  # Replace if using custom trained model

# ========== Cooldown Filter ==========
last_detection_time = {}

def should_save_detection(label, room):
    now = datetime.now()
    if room not in last_detection_time:
        last_detection_time[room] = {}
    if label not in last_detection_time[room] or (now - last_detection_time[room][label]).total_seconds() > 120:
        last_detection_time[room][label] = now
        return True
    return False

def get_detection_status():
    if os.path.exists(DETECTION_STATE_FILE):
        with open(DETECTION_STATE_FILE, 'r') as f:
            return json.load(f).get("status", "active")
    return "active"

# ========== Main Detection Function ==========
def run_detection_for_camera(camera_config):
    room = camera_config['room']
    source = camera_config['source']
    ip = camera_config['ip']
    url = f"{ip}/video" if not ip.endswith('/video') else ip

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"❌ Could not open stream: {room} ({url})")
        return

    print(f"✅ Running detection for: {room} ({url})")

    while True:
        if get_detection_status() == "paused":
            print(f"⏸️ Detection paused for {room}")
            time.sleep(5)
            continue

        ret, frame = cap.read()
        if not ret:
            print(f"⚠️ Lost stream from {room}, retrying...")
            cap.release()
            time.sleep(5)
            cap = cv2.VideoCapture(url)
            continue

        results = model(frame)[0]
        for box in results.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            if label.lower() in ['mobile phone', 'cell phone', 'phone']:
                if should_save_detection(label, room):
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"{room}_{source}_{timestamp}.jpg"
                    filepath = os.path.join(SCREENSHOT_FOLDER, filename)
                    cv2.imwrite(filepath, frame)

                    payload = {
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'room': room,
                        'label': 'Mobile Detected',
                        'filename': filename
                    }
                    try:
                        res = requests.post(SERVER_URL, json=payload)
                        res.raise_for_status()
                        print(f"📤 Log sent: {room} → Mobile Detected")
                    except Exception as e:
                        print(f"❌ Log upload failed for {room}: {e}")

    cap.release()

# ========== Start for All Cameras ==========
if __name__ == '__main__':
    if not os.path.exists(CAM_CONFIG_FILE):
        print(f"❌ {CAM_CONFIG_FILE} not found.")
        exit()

    with open(CAM_CONFIG_FILE, 'r') as f:
        cameras = json.load(f)

    if not cameras:
        print("❌ No cameras configured.")
        exit()

    print(f"🚀 Starting detection for {len(cameras)} camera(s)...\n")

    threads = []
    for cam in cameras:
        t = threading.Thread(target=run_detection_for_camera, args=(cam,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
