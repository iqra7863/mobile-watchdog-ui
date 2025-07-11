from flask import Flask, render_template, request, redirect, session, url_for, send_file, send_from_directory, jsonify
import os
import json
from datetime import datetime
import glob

app = Flask(__name__)
app.secret_key = 'guardian_secret'

# Config files and folders
CAM_CONFIG_FILE = 'camera_config.json'
USER_FILE = 'users.json'
SCREENSHOT_FOLDER = 'screenshots'
LOG_FILE = 'logs.csv'
STATE_FILE = 'detection_state.json'

# Ensure screenshot folder exists
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# ----------- Utility Functions --------------
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    return {}

def load_cameras():
    if os.path.exists(CAM_CONFIG_FILE):
        with open(CAM_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return []

def save_cameras(cameras):
    with open(CAM_CONFIG_FILE, 'w') as f:
        json.dump(cameras, f, indent=4)

# ----------- Login Routes --------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        users = load_users()
        if user in users and users[user]['password'] == pwd:
            session['username'] = user
            session['role'] = users[user]['role']
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ----------- Dashboard --------------
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')

    cameras = load_cameras()
    logs = []

    # Load recent logs
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            for line in lines[-50:]:  # last 50 logs
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    logs.append({
                        'timestamp': parts[0],
                        'room': parts[1],
                        'label': parts[2]
                    })

    # Load recent screenshots
    images = []
    all_images = glob.glob(os.path.join(SCREENSHOT_FOLDER, '*.jpg'))
    all_images.sort(key=os.path.getmtime, reverse=True)
    for img in all_images[:20]:
        parts = os.path.basename(img).split('_')
        room = parts[0] if len(parts) > 0 else 'Unknown'
        images.append({'file': os.path.basename(img), 'room': room})

    return render_template('dashboard.html', logs=logs, images=images, cameras=cameras, session=session)
@app.route('/get_logs')
def get_logs():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            for line in lines[-50:]:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    logs.append({
                        'timestamp': parts[0],
                        'room': parts[1],
                        'label': parts[2]
                    })
    return jsonify(logs)

# ----------- Mobile Dashboard --------------
@app.route('/mobile_dashboard')
def mobile_dashboard():
    cameras = load_cameras()
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            for line in lines[-50:]:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    logs.append({'timestamp': parts[0], 'room': parts[1], 'label': parts[2]})

    images = []
    all_images = glob.glob(os.path.join(SCREENSHOT_FOLDER, '*.jpg'))
    all_images.sort(key=os.path.getmtime, reverse=True)
    for img in all_images[:20]:
        parts = os.path.basename(img).split('_')
        room = parts[0] if len(parts) > 0 else 'Unknown'
        images.append({'file': os.path.basename(img), 'room': room})

    return render_template('mobile_dashboard.html', logs=logs, images=images, cameras=cameras)

# ----------- Camera Management --------------
@app.route('/add_camera', methods=['POST'])
def add_camera():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    ip = request.form['ip']
    room = request.form['room']
    source = request.form['source']
    cameras = load_cameras()
    if not any(c['ip'] == ip for c in cameras):
        cameras.append({'ip': ip, 'room': room, 'source': source})
        save_cameras(cameras)
    return redirect('/dashboard')

@app.route('/remove_camera/<path:ip_encoded>')
def remove_camera(ip_encoded):
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    ip = ip_encoded.replace('__SLASH__', '/')
    cameras = load_cameras()
    cameras = [c for c in cameras if c['ip'] != ip]
    save_cameras(cameras)
    return redirect('/dashboard')

# ----------- Live View Per Camera --------------
@app.route('/camera_view')
def camera_view():
    ip = request.args.get('ip')
    cameras = load_cameras()
    camera = next((c for c in cameras if c['ip'] == ip), None)

    logs = []
    images = []

    if camera:
        # Filter logs by room
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split(',')
                    if len(parts) >= 3 and parts[1] == camera['room']:
                        logs.append({'timestamp': parts[0], 'label': parts[2]})

        # Filter screenshots by room
        all_images = glob.glob(os.path.join(SCREENSHOT_FOLDER, '*.jpg'))
        all_images.sort(key=os.path.getmtime, reverse=True)
        for img in all_images:
            parts = os.path.basename(img).split('_')
            room = parts[0] if len(parts) > 0 else 'Unknown'
            images.append({'file': os.path.basename(img), 'room': room})

        return render_template('camera_view.html', camera=camera, logs=logs, images=images)

    return "Camera not found", 404

# ----------- Pause / Resume Detection --------------
@app.route('/pause', methods=['POST'])
def pause_detection():
    with open(STATE_FILE, 'w') as f:
        json.dump({"status": "paused"}, f)
    return redirect('/dashboard')

@app.route('/resume', methods=['POST'])
def resume_detection():
    with open(STATE_FILE, 'w') as f:
        json.dump({"status": "active"}, f)
    return redirect('/dashboard')

# ----------- Clear Per Room --------------
@app.route('/clear_room/<room>')
def clear_room(room):
    # Delete screenshots of this room
    for file in os.listdir(SCREENSHOT_FOLDER):
        if file.startswith(room + '_'):
            os.remove(os.path.join(SCREENSHOT_FOLDER, file))
    # Remove logs of this room
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        with open(LOG_FILE, 'w') as f:
            for line in lines:
                if f',{room},' not in line:
                    f.write(line)
    return redirect('/dashboard')

# ----------- Screenshot Serving --------------
@app.route('/screenshots/<filename>')
def get_screenshot(filename):
    return send_from_directory(SCREENSHOT_FOLDER, filename)

# ----------- Download Logs --------------
@app.route('/download_logs')
def download_logs():
    return send_file(LOG_FILE, as_attachment=True)

# ----------- Initialize --------------
if __name__ == '__main__':
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'w') as f:
            json.dump({"status": "active"}, f)
    app.run(host='0.0.0.0', port=5000, debug=True)
