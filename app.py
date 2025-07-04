from flask import Flask, render_template, request, redirect, session, url_for, send_file, send_from_directory
import os
import json
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

# Load users
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    return {}

# Load and Save cameras
def load_cameras():
    if os.path.exists(CAM_FILE):
        with open(CAM_FILE, 'r') as f:
            return json.load(f)
    return []

def save_cameras(cameras):
    with open(CAM_FILE, 'w') as f:
        json.dump(cameras, f, indent=4)

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

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/')

    # Load Logs
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    parts = line.strip().split(',')
                    if len(parts) == 3:
                        logs.append({
                            'timestamp': parts[0],
                            'room': parts[1],
                            'label': parts[2]
                        })
        except Exception as e:
            print("Log file read error:", e)

    # Load Screenshots
    try:
        images = sorted(os.listdir(SCREENSHOT_FOLDER), reverse=True)[:10]
    except Exception as e:
        print("Screenshot folder read error:", e)
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

@app.route('/screenshots/<filename>')
def get_screenshot(filename):
    return send_from_directory(SCREENSHOT_FOLDER, filename)

@app.route('/camera_view')
def camera_view():
    ip = request.args.get('ip')
    cameras = load_cameras()
    camera = next((c for c in cameras if c['ip'] == ip), None)
    return render_template('camera_view.html', camera=camera)

@app.route('/pause', methods=['POST'])
def pause_detection():
    return redirect('/dashboard')

@app.route('/resume', methods=['POST'])
def resume_detection():
    return redirect('/dashboard')

@app.route('/upload_log', methods=['POST'])
def upload_log():
    data = request.get_json()
    with open(LOG_FILE, 'a') as f:
        f.write(f"{data['timestamp']},{data['room']},{data['label']}\n")
    return 'OK'

@app.route('/mobile_dashboard')
def mobile_dashboard():
    if 'username' not in session:
        return redirect('/')
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                parts = line.strip().split(',')
                if len(parts) == 3:
                    logs.append({
                        'timestamp': parts[0],
                        'room': parts[1],
                        'label': parts[2]
                    })
    images = sorted(os.listdir(SCREENSHOT_FOLDER), reverse=True)[:10]
    cameras = load_cameras()
    return render_template('mobile_dashboard.html', logs=logs, images=images, cameras=cameras)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
