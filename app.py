from flask import Flask, render_template, request, redirect, session, url_for, send_file
import os
import json
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'guardian_secret'

CAM_FILE = 'camera_config.json'
USER_FILE = 'users.json'
SCREENSHOT_FOLDER = 'screenshots'
LOG_FILE = 'logs.csv'

# Ensure screenshot folder exists
if not os.path.exists(SCREENSHOT_FOLDER):
    os.makedirs(SCREENSHOT_FOLDER)

# Load users securely
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    return {}

# Load Cameras
def load_cameras():
    if os.path.exists(CAM_FILE):
        with open(CAM_FILE, 'r') as f:
            return json.load(f)
    return []

# Save Cameras
def save_cameras(cameras):
    with open(CAM_FILE, 'w') as f:
        json.dump(cameras, f, indent=4)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        # Force re-load users on every login
        if os.path.exists(USER_FILE):
            with open(USER_FILE, 'r') as f:
                users = json.load(f)
        else:
            users = {}

        if user in users and users[user]['password'] == pwd:
            session['username'] = user
            session['role'] = users[user]['role']
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')

    logs = []
    if os.path.exists(LOG_FILE):
        try:
            df = pd.read_csv(LOG_FILE)
            df = df.tail(20)
            logs = df.to_dict('records')
        except Exception as e:
            print(f"Error loading logs: {e}")

    try:
        images = sorted(os.listdir(SCREENSHOT_FOLDER), reverse=True)[:10]
    except:
        images = []

    cameras = load_cameras()
    return render_template('dashboard.html', logs=logs, images=images, role=session['role'], cameras=cameras, session=session)

@app.route('/add_camera', methods=['POST'])
def add_camera():
    ip = request.form['ip']
    room = request.form['room']
    source = request.form['source']
    cameras = load_cameras()
    cameras.append({'ip': ip, 'room': room, 'source': source})
    save_cameras(cameras)
    return redirect('/dashboard')

@app.route('/remove_camera/<ip>')
def remove_camera(ip):
    cameras = load_cameras()
    cameras = [c for c in cameras if c['ip'] != ip]
    save_cameras(cameras)
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/download_logs')
def download_logs():
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, as_attachment=True)
    return "Log file not found."

@app.route('/clear_screenshots')
def clear_screenshots():
    for f in os.listdir(SCREENSHOT_FOLDER):
        os.remove(os.path.join(SCREENSHOT_FOLDER, f))
    return redirect('/dashboard')

@app.route('/camera/<ip>')
def camera_view(ip):
    cameras = load_cameras()
    camera = next((c for c in cameras if c['ip'] == ip), None)
    return render_template('camera_view.html', camera=camera)

# Optional pause/resume buttons (connect with detect_api if needed)
@app.route('/pause', methods=['POST'])
def pause_detection():
    return redirect('/dashboard')

@app.route('/resume', methods=['POST'])
def resume_detection():
    return redirect('/dashboard')

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
