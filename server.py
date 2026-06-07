import subprocess
import sys
import json
import shlex

try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors"])
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS

import os
import threading
import time
import shutil

app = Flask(__name__, static_folder='.')
CORS(app)

UPLOAD_FOLDER = 'uploaded'
LOG_FOLDER = 'logs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/files')
def list_files():
    files = []
    if os.path.exists(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            fp = os.path.join(UPLOAD_FOLDER, f)
            if os.path.isfile(fp):
                files.append({
                    'name': f,
                    'size': os.path.getsize(fp),
                    'modified': time.ctime(os.path.getmtime(fp))
                })
    files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x['name'])), reverse=True)
    return jsonify({'files': files})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'error': 'No file selected'}), 400
    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return jsonify({'status': 'ok', 'filename': filename})

@app.route('/api/delete', methods=['POST'])
def delete_file():
    data = request.get_json()
    filename = data.get('filename', '')
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'error': 'File not found'}), 404

@app.route('/api/run', methods=['POST'])
def run_file():
    data = request.get_json()
    filename = data.get('filename', '')
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'error': 'File not found'}), 404
    try:
        result = subprocess.run(
            [sys.executable, filepath],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=UPLOAD_FOLDER,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        output = ''
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += '\n' + result.stderr
        return jsonify({
            'status': 'ok' if result.returncode == 0 else 'error',
            'output': output.strip(),
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'error': 'Execution timeout (300s)'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/pip_install', methods=['POST'])
def pip_install():
    data = request.get_json()
    package = data.get('package', '').strip()
    if not package:
        return jsonify({'status': 'error', 'error': 'No package specified'}), 400
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package],
            capture_output=True,
            text=True,
            timeout=600
        )
        output = result.stdout + '\n' + result.stderr
        return jsonify({
            'status': 'ok' if result.returncode == 0 else 'error',
            'output': output.strip(),
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'error': 'Install timeout (600s)'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/install_requirements', methods=['POST'])
def install_requirements():
    req_path = os.path.join(UPLOAD_FOLDER, 'requirements.txt')
    if not os.path.exists(req_path):
        return jsonify({'status': 'error', 'error': 'requirements.txt not found in uploaded folder'}), 404
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', req_path],
            capture_output=True,
            text=True,
            timeout=600
        )
        output = result.stdout + '\n' + result.stderr
        return jsonify({
            'status': 'ok' if result.returncode == 0 else 'error',
            'output': output.strip(),
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        })
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'error': 'Install timeout (600s)'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == '__main__':
    print("""
    ⚡⚡⚡ MAHIR HOSTING SERVER ⚡⚡⚡
    🟢 Server running on: http://0.0.0.0:5000
    📂 Upload folder: ./uploaded/
    📜 Log folder: ./logs/
    
    Open your browser and go to: http://localhost:5000
    """)
    app.run(host='0.0.0.0', port=5000, debug=True)