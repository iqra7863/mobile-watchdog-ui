from flask import Flask, render_template, request, redirect, session, url_for, send_file, send_from_directory, jsonify
import os
import json
from datetime import datetime
import glob

app = Flask(__name__)
app.secret_key = 'guardian_secret'

# Config files
CAM_CONFIG_FILE = 'camera_config.json'
USER_FILE = 'users.json'
SCREENSHOT_FOLDER = 'screenshots'
LOG_FILE = 'logs.csv'
STATE_FILE = 'detection_state.json'

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# ---------- Utility Functions ----------
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
        json.dump(cameras, f, indent=2)

def read_logs():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    logs.append({
                        'timestamp': parts[0],
                        'room': parts[1],
                        'label': parts[2]
                    })
    return logs

def get_images_for_class(classroom):
    images = []
    all_images = glob.glob(os.path.join(SCREENSHOT_FOLDER, f'{classroom}_*.jpg'))
    all_images.sort(key=os.path.getmtime, reverse=True)
    for img in all_images[:20]:
        images.append({'file': os.path.basename(img), 'room': classroom})
    return images

# ---------- Routes ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        users = load_users()
        if user in users and users[user]['password'] == pwd:
            session['username'] = user
            session['role'] = users[user]['role']
            session['allowed_classes'] = users[user].get('allowed_classes', [])
            session['selected_class'] = session['allowed_classes'][0] if session['allowed_classes'] else None
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/set_classroom', methods=['POST'])
def set_classroom():
    session['selected_class'] = request.form.get('selected_classroom')
    return redirect('/dashboard')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect('/')

    selected_class = session.get('selected_class')
    allowed_classes = session.get('allowed_classes', [])
    cameras = load_cameras()
    logs = [log for log in read_logs() if log['room'] == selected_class]
    images = get_images_for_class(selected_class)

    return render_template('dashboard.html',
                           logs=logs,
                           screenshots=images,
                           cameras=cameras,
                           session=session,
                           selected_classroom=selected_class,
                           allowed_classes=allowed_classes)

@app.route('/get_logs')
def get_logs():
    if 'username' not in session:
        return jsonify([])
    selected = session.get('selected_class')
    logs = [log for log in read_logs() if log['room'] == selected]
    return jsonify(logs)

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
    cameras = [c for c in load_cameras() if c['ip'] != ip]
    save_cameras(cameras)
    return redirect('/dashboard')

@app.route('/camera_view')
def camera_view():
    if 'username' not in session:
        return redirect('/')
    ip = request.args.get('ip')
    cameras = load_cameras()
    camera = next((c for c in cameras if c['ip'] == ip), None)
    if not camera:
        return "Camera not found", 404
    room = camera['room']
    logs = [log for log in read_logs() if log['room'] == room]
    images = get_images_for_class(room)
    return render_template('camera_view.html', camera=camera, logs=logs, images=images)

@app.route('/pause', methods=['POST'])
def pause_detection():
    with open(STATE_FILE, 'w') as f:
        json.dump({'status': 'paused'}, f)
    return redirect('/dashboard')

@app.route('/resume', methods=['POST'])
def resume_detection():
    with open(STATE_FILE, 'w') as f:
        json.dump({'status': 'active'}, f)
    return redirect('/dashboard')

@app.route('/clear_room/<room>')
def clear_room(room):
    for file in os.listdir(SCREENSHOT_FOLDER):
        if file.startswith(f'{room}_'):
            os.remove(os.path.join(SCREENSHOT_FOLDER, file))
    logs = read_logs()
    logs = [log for log in logs if log['room'] != room]
    with open(LOG_FILE, 'w') as f:
        for log in logs:
            f.write(f"{log['timestamp']},{log['room']},{log['label']}\n")
    return redirect('/dashboard')

@app.route('/screenshots/<filename>')
def get_screenshot(filename):
    return send_from_directory(SCREENSHOT_FOLDER, filename)

@app.route('/download_logs')
def download_logs():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    return send_file(LOG_FILE, as_attachment=True)

# ---------- Mobile Dashboard ----------
@app.route('/mobile_dashboard', methods=['GET', 'POST'])
def mobile_dashboard():
    if 'username' not in session:
        return redirect('/')

    allowed_classes = session.get('allowed_classes', [])
    if not allowed_classes:
        return "No classroom access configured", 403

    # Handle classroom switch
    if request.method == 'POST':
        session['selected_class'] = request.form.get('selected_class')

    selected_class = session.get('selected_class', allowed_classes[0])
    logs = [log for log in read_logs() if log['room'] == selected_class]
    images = get_images_for_class(selected_class)

    return render_template('mobile_dashboard.html',
                           logs=logs,
                           images=images,
                           selected_class=selected_class,
                           allowed_classes=allowed_classes)
# ---------- Init ----------
if __name__ == '__main__':
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'w') as f:
            json.dump({'status': 'active'}, f)
    app.run(host='0.0.0.0', port=5000, debug=True)
