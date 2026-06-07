#!/usr/bin/env python3
"""
MAHIR HOSTING SERVER - Main Starter
Python 3.13+ Compatible
"""

import os
import sys
import subprocess
import time
import socket
import threading
import json
import shutil
import zipfile
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import email.parser
import io
import tempfile

# ============ কনফিগারেশন ============
HOST = '0.0.0.0'
PORT = 5000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploaded')
EXTRACT_DIR = os.path.join(BASE_DIR, 'extracted')
LOG_FILE = os.path.join(BASE_DIR, 'server.log')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

# ============ গ্লোবাল লগ সিস্টেম ============
log_lines = []
log_lock = threading.Lock()

def add_log(message, level='info'):
    timestamp = time.strftime('%H:%M:%S')
    log_entry = {
        'time': timestamp,
        'message': message,
        'level': level
    }
    with log_lock:
        log_lines.append(log_entry)
        if len(log_lines) > 500:
            log_lines.pop(0)
    
    color = '\033[92m' if level == 'success' else '\033[91m' if level == 'error' else '\033[93m' if level == 'warning' else '\033[0m'
    print(f"{color}[{timestamp}] {message}\033[0m")
    
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{level.upper()}] {message}\n")
    except:
        pass

# ============ Multipart parser (Python 3.13 compatible) ============
def parse_multipart(headers, body):
    """Python 3.13 compatible multipart parser - NO cgi module"""
    content_type = headers.get('Content-Type', '')
    
    if 'multipart/form-data' not in content_type:
        return None
    
    # Extract boundary
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part[9:].strip('"')
            break
    
    if not boundary:
        return None
    
    boundary_bytes = boundary.encode('utf-8')
    body_bytes = body if isinstance(body, bytes) else body.encode('utf-8')
    
    # Split by boundary
    delimiter = b'--' + boundary_bytes
    parts = body_bytes.split(delimiter)
    
    files = {}
    form_fields = {}
    
    for part in parts:
        if not part or part == b'--' or part == b'--\r\n' or part == b'\r\n':
            continue
        
        # Remove leading \r\n
        if part.startswith(b'\r\n'):
            part = part[2:]
        
        # Find header/body separator
        separator_pos = part.find(b'\r\n\r\n')
        if separator_pos == -1:
            continue
        
        header_section = part[:separator_pos].decode('utf-8', errors='ignore')
        body_section = part[separator_pos + 4:]
        
        # Remove trailing \r\n
        if body_section.endswith(b'\r\n'):
            body_section = body_section[:-2]
        
        # Parse headers
        header_dict = {}
        for line in header_section.split('\r\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                header_dict[key.strip().lower()] = value.strip()
        
        # Check if this is a file
        disposition = header_dict.get('content-disposition', '')
        
        if 'filename=' in disposition:
            # Extract filename
            filename = None
            for dpart in disposition.split(';'):
                dpart = dpart.strip()
                if dpart.startswith('filename='):
                    filename = dpart[9:].strip('"')
                    break
            
            # Extract field name
            field_name = 'file'
            for dpart in disposition.split(';'):
                dpart = dpart.strip()
                if dpart.startswith('name='):
                    field_name = dpart[5:].strip('"')
                    break
            
            if filename:
                if field_name not in files:
                    files[field_name] = []
                files[field_name].append({
                    'filename': filename,
                    'data': body_section,
                    'content_type': header_dict.get('content-type', 'application/octet-stream')
                })
        else:
            # Regular form field
            field_name = None
            for dpart in disposition.split(';'):
                dpart = dpart.strip()
                if dpart.startswith('name='):
                    field_name = dpart[5:].strip('"')
                    break
            if field_name:
                form_fields[field_name] = body_section.decode('utf-8', errors='ignore')
    
    return {'files': files, 'fields': form_fields}


# ============ ফাইল রান ফাংশন ============
def run_python_file(filepath):
    add_log(f"▶ Executing: {os.path.basename(filepath)}", 'info')
    
    try:
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"
        
        process = subprocess.run(
            [sys.executable, filepath],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.path.dirname(filepath),
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        output = ""
        if process.stdout:
            output += process.stdout
        if process.stderr:
            if output:
                output += "\n"
            output += process.stderr
        
        if process.returncode == 0:
            add_log(f"✅ {os.path.basename(filepath)} completed", 'success')
        else:
            add_log(f"❌ {os.path.basename(filepath)} exit code: {process.returncode}", 'error')
        
        return True, output.strip() if output.strip() else "(No output)"
        
    except subprocess.TimeoutExpired:
        add_log(f"⏰ {os.path.basename(filepath)} timeout 300s", 'error')
        return False, "Execution timeout (300 seconds)"
    except Exception as e:
        add_log(f"💥 Error: {str(e)}", 'error')
        return False, f"Error: {str(e)}\n{traceback.format_exc()}"

def install_pip_package(package_name):
    add_log(f"📦 Installing: {package_name}", 'info')
    
    try:
        process = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package_name],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        output = process.stdout + "\n" + process.stderr
        
        if process.returncode == 0:
            add_log(f"✅ {package_name} installed", 'success')
        else:
            add_log(f"❌ Failed: {package_name}", 'error')
        
        return process.returncode == 0, output.strip()
        
    except Exception as e:
        add_log(f"💥 Install error: {str(e)}", 'error')
        return False, str(e)

def install_requirements_file(req_path):
    add_log(f"📋 Installing from requirements.txt", 'info')
    
    try:
        process = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', req_path],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        output = process.stdout + "\n" + process.stderr
        
        if process.returncode == 0:
            add_log(f"✅ All requirements installed", 'success')
        else:
            add_log(f"❌ Some failed", 'error')
        
        return process.returncode == 0, output.strip()
        
    except Exception as e:
        add_log(f"💥 Error: {str(e)}", 'error')
        return False, str(e)

def extract_zip(zip_path):
    add_log(f"📦 Extracting: {os.path.basename(zip_path)}", 'info')
    
    try:
        folder_name = os.path.splitext(os.path.basename(zip_path))[0]
        extract_path = os.path.join(EXTRACT_DIR, folder_name)
        
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        
        os.makedirs(extract_path, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        file_count = sum([len(files) for _, _, files in os.walk(extract_path)])
        add_log(f"✅ Extracted {file_count} files to: {folder_name}/", 'success')
        
        return True, f"Extracted {file_count} files"
        
    except Exception as e:
        add_log(f"💥 Extract error: {str(e)}", 'error')
        return False, str(e)

# ============ HTTP হ্যান্ডলার ============
class MAHIRHostingHandler(SimpleHTTPRequestHandler):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/status':
            self.api_status()
        elif path == '/api/files':
            self.api_list_files()
        elif path == '/api/logs':
            self.api_get_logs()
        elif path == '/api/extracted':
            self.api_list_extracted()
        elif path.startswith('/download/'):
            self.serve_download(path)
        else:
            if path == '/' or path == '':
                self.path = '/index.html'
            super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/upload':
            self.api_upload()
        elif path == '/api/run':
            self.api_run()
        elif path == '/api/delete':
            self.api_delete()
        elif path == '/api/pip':
            self.api_pip()
        elif path == '/api/requirements':
            self.api_requirements()
        elif path == '/api/unzip':
            self.api_unzip()
        elif path == '/api/run-extracted':
            self.api_run_extracted()
        else:
            self.send_error(404)
    
    def api_status(self):
        files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
        extracted = os.listdir(EXTRACT_DIR) if os.path.exists(EXTRACT_DIR) else []
        self.send_json({
            'status': 'online',
            'files': len(files),
            'extracted': len(extracted),
            'uptime': time.time()
        })
    
    def api_list_files(self):
        files = []
        if os.path.exists(UPLOAD_DIR):
            for f in os.listdir(UPLOAD_DIR):
                fp = os.path.join(UPLOAD_DIR, f)
                if os.path.isfile(fp):
                    files.append({
                        'name': f,
                        'size': os.path.getsize(fp),
                        'modified': time.ctime(os.path.getmtime(fp)),
                        'ext': os.path.splitext(f)[1].lower()
                    })
        files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x['name'])), reverse=True)
        self.send_json({'files': files})
    
    def api_list_extracted(self):
        folders = []
        if os.path.exists(EXTRACT_DIR):
            for d in os.listdir(EXTRACT_DIR):
                dp = os.path.join(EXTRACT_DIR, d)
                if os.path.isdir(dp):
                    py_files = []
                    for root, _, filenames in os.walk(dp):
                        for f in filenames:
                            if f.endswith('.py'):
                                rel_path = os.path.relpath(os.path.join(root, f), EXTRACT_DIR)
                                py_files.append(rel_path)
                    folders.append({
                        'name': d,
                        'files': len(py_files),
                        'py_files': py_files
                    })
        self.send_json({'folders': folders})
    
    def api_get_logs(self):
        with log_lock:
            logs = list(log_lines[-100:])
        self.send_json({'logs': logs})
    
    def api_upload(self):
        content_type = self.headers.get('Content-Type', '')
        content_length = int(self.headers.get('Content-Length', 0))
        
        if content_length == 0:
            self.send_json({'status': 'error', 'message': 'No file'})
            return
        
        body = self.rfile.read(content_length)
        
        if 'multipart/form-data' in content_type:
            parsed = parse_multipart(self.headers, body)
            
            if parsed and parsed['files']:
                uploaded = []
                for field_name, file_list in parsed['files'].items():
                    for file_info in file_list:
                        filename = os.path.basename(file_info['filename'])
                        if filename:
                            saved = self.save_file(filename, file_info['data'])
                            if saved:
                                uploaded.append(saved)
                
                if uploaded:
                    self.send_json({'status': 'ok', 'files': uploaded})
                else:
                    self.send_json({'status': 'error', 'message': 'Failed to save files'})
            else:
                self.send_json({'status': 'error', 'message': 'No files in request'})
        else:
            self.send_json({'status': 'error', 'message': 'Use multipart/form-data'})
    
    def save_file(self, filename, data):
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        # ওভাররাইট হলে নাম্বার যোগ
        counter = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(filepath):
            filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            counter += 1
        
        with open(filepath, 'wb') as f:
            f.write(data)
        
        add_log(f"📤 Uploaded: {filename}", 'success')
        
        # ZIP হলে অটো এক্সট্রাক্ট
        if filename.lower().endswith('.zip'):
            threading.Thread(target=extract_zip, args=(filepath,), daemon=True).start()
        
        return filename
    
    def api_run(self):
        data = self.get_json_body()
        filename = data.get('filename', '')
        
        if not filename:
            self.send_json({'status': 'error', 'message': 'No filename'})
            return
        
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        if not os.path.exists(filepath):
            self.send_json({'status': 'error', 'message': f'File not found: {filename}'})
            return
        
        success, output = run_python_file(filepath)
        
        self.send_json({
            'status': 'ok' if success else 'error',
            'output': output,
            'filename': filename
        })
    
    def api_run_extracted(self):
        data = self.get_json_body()
        filepath_rel = data.get('filepath', '')
        
        if not filepath_rel:
            self.send_json({'status': 'error', 'message': 'No filepath'})
            return
        
        full_path = os.path.join(EXTRACT_DIR, filepath_rel)
        
        if not os.path.exists(full_path):
            self.send_json({'status': 'error', 'message': f'File not found: {filepath_rel}'})
            return
        
        success, output = run_python_file(full_path)
        
        self.send_json({
            'status': 'ok' if success else 'error',
            'output': output,
            'filepath': filepath_rel
        })
    
    def api_delete(self):
        data = self.get_json_body()
        filename = data.get('filename', '')
        type_ = data.get('type', 'uploaded')
        
        if type_ == 'extracted':
            filepath = os.path.join(EXTRACT_DIR, filename)
        else:
            filepath = os.path.join(UPLOAD_DIR, filename)
        
        if os.path.exists(filepath):
            if os.path.isdir(filepath):
                shutil.rmtree(filepath)
            else:
                os.remove(filepath)
            add_log(f"🗑 Deleted: {filename}", 'warning')
            self.send_json({'status': 'ok'})
        else:
            self.send_json({'status': 'error', 'message': 'Not found'})
    
    def api_pip(self):
        data = self.get_json_body()
        package = data.get('package', '').strip()
        
        if not package:
            self.send_json({'status': 'error', 'message': 'No package name'})
            return
        
        success, output = install_pip_package(package)
        
        self.send_json({
            'status': 'ok' if success else 'error',
            'output': output,
            'package': package
        })
    
    def api_requirements(self):
        req_path = os.path.join(UPLOAD_DIR, 'requirements.txt')
        
        if not os.path.exists(req_path):
            self.send_json({'status': 'error', 'message': 'Upload requirements.txt first'})
            return
        
        success, output = install_requirements_file(req_path)
        
        self.send_json({
            'status': 'ok' if success else 'error',
            'output': output
        })
    
    def api_unzip(self):
        data = self.get_json_body()
        filename = data.get('filename', '')
        
        if not filename:
            self.send_json({'status': 'error', 'message': 'No filename'})
            return
        
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        if not os.path.exists(filepath):
            self.send_json({'status': 'error', 'message': 'File not found'})
            return
        
        success, message = extract_zip(filepath)
        
        self.send_json({
            'status': 'ok' if success else 'error',
            'message': message
        })
    
    def serve_download(self, path):
        parts = path.replace('/download/', '').split('/', 1)
        if len(parts) >= 2:
            type_, filepath = parts[0], parts[1]
            if type_ == 'uploaded':
                full_path = os.path.join(UPLOAD_DIR, filepath)
            else:
                full_path = os.path.join(EXTRACT_DIR, filepath)
            
            if os.path.exists(full_path) and os.path.isfile(full_path):
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(full_path)}"')
                self.end_headers()
                with open(full_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
        
        self.send_error(404)
    
    def get_json_body(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                return json.loads(body.decode('utf-8'))
        except:
            pass
        return {}
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        pass

# ============ IP ============
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

# ============ মেইন ============
if __name__ == '__main__':
    local_ip = get_local_ip()
    
    print("""
╔══════════════════════════════════════════════════╗
║      ⚡ MAHIR HOSTING SERVER ⚡                  ║
║      PREMIUM VIP SERVER                         ║
╚══════════════════════════════════════════════════╝
    """)
    print(f"🟢 Server Started!")
    print(f"📍 Local:   http://localhost:{PORT}")
    print(f"📍 Network: http://{local_ip}:{PORT}")
    print(f"📂 Uploads: {UPLOAD_DIR}")
    print(f"📦 Extracted: {EXTRACT_DIR}")
    print(f"📜 Log: {LOG_FILE}")
    print(f"\n✨ Browser e open koro!\n")
    
    add_log("🚀 Server started", 'success')
    add_log(f"📍 http://{local_ip}:{PORT}", 'info')
    
    server = HTTPServer((HOST, PORT), MAHIRHostingHandler)
    
    try:
        print("Press Ctrl+C to stop\n")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        add_log("🛑 Server stopped", 'warning')
        server.shutdown()