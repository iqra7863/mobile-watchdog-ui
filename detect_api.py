from flask import Flask
import os, json, cv2
from ultralytics import YOLO
from datetime import datetime
import csv
import threading
import time

app = Flask(__name__)
SCREENSHOT_DIR = "screenshots"
LOG_FILE = "logs.csv"
CAM_FILE = "cameras.json"
DETECTION_INTERVAL = 2  # seconds

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

model = YOLO("yolov8n.pt")

def log_detection(room, status):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), room, status])

def save_screenshot(frame, room, source):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{room}_{source}_{timestamp}.jpg"
    path = os.path.join(SCREENSHOT_DIR, filename)
    cv2.imwrite(path, frame)

def detect(cam):
    cap = cv2.VideoCapture(cam['ip'] + "/video")
    if not cap.isOpened():
        print(f"[ERROR] Failed to open {cam['room']} - {cam['ip']}")
        return

    while True:
        ret, frame = cap.read()
        if not ret: break
        results = model.predict(frame, imgsz=640, conf=0.5)
        for r in results:
            if r.boxes:
                log_detection(cam['room'], "Mobile Detected")
                save_screenshot(frame, cam['room'], cam['source'])
        time.sleep(DETECTION_INTERVAL)

@app.route('/')
def index():
    return "YOLO Detection Running"

def start_detection():
    with open(CAM_FILE) as f:
        cams = json.load(f)
    for cam in cams:
        threading.Thread(target=detect, args=(cam,), daemon=True).start()

if __name__ == '__main__':
    start_detection()
    app.run(host="0.0.0.0", port=5001)
