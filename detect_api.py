import cv2
import requests
from datetime import datetime
import os
from ultralytics import YOLO

# ========== CONFIG ==========
CAMERA_URL = 'http://100.76.202.108:8080/video'  # Your Mobile IP Webcam
SERVER_URL = 'http://127.0.0.1:5000/upload_log'  # Your Flask server URL
ROOM_NAME = '1'  # e.g., Lab 1, Room A
CAMERA_SOURCE = 'Mobile'
DETECTION_CLASS = 'mobile phone'  # class name in YOLO model

SCREENSHOT_FOLDER = 'screenshots'
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# ========== Load YOLO Model ==========
model = YOLO('yolov8n.pt')  # Use your custom model here if needed

# ========== Time Filter ==========
last_detection_time = {}

def should_save_detection(label):
    now = datetime.now()
    if label not in last_detection_time or (now - last_detection_time[label]).total_seconds() > 120:
        last_detection_time[label] = now
        return True
    return False

# ========== Start Capture ==========
cap = cv2.VideoCapture(CAMERA_URL)

if not cap.isOpened():
    print("❌ Failed to open camera stream.")
    exit()

print("✅ Detection Started...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to grab frame.")
        break

    # Detect
    results = model(frame)[0]
    for box in results.boxes:
        cls = int(box.cls[0])
        label = model.names[cls]
        if label.lower() in ['mobile phone', 'cell phone', 'phone'] and should_save_detection(label):
            # Save screenshot
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{ROOM_NAME}_{CAMERA_SOURCE}_{timestamp}.jpg"
            filepath = os.path.join(SCREENSHOT_FOLDER, filename)
            cv2.imwrite(filepath, frame)

            # Upload log to server
            payload = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'room': ROOM_NAME,
                'label': 'Mobile Detected',
                'filename': filename
            }
            try:
                res = requests.post(SERVER_URL, json=payload)
                print("✅ Uploaded:", payload)
            except Exception as e:
                print("❌ Upload failed:", e)

    # Optional: Show preview window
    cv2.imshow("Live Detection", frame)
    if cv2.waitKey(1) == 27:  # ESC to quit
        break

cap.release()
cv2.destroyAllWindows()
