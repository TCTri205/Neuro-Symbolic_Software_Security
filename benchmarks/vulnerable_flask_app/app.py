import sqlite3
import subprocess
import pickle
import yaml
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# A02: Hardcoded Secret
API_KEY = "sk_live_12345_THIS_IS_A_SECRET_KEY"

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return "Vulnerable App Running"

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    # A02: Weak Crypto (MD5)
    hashed_password = hashlib.md5(password.encode()).hexdigest()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # A01: SQL Injection
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{hashed_password}'"
    print(f"Executing: {query}")
    cursor.execute(query)
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return jsonify({"status": "success", "user": dict(user)})
    else:
        return jsonify({"status": "failure"}), 401

@app.route('/ping', methods=['GET'])
def ping():
    target = request.args.get('target', 'localhost')
    
    # A01: Command Injection
    # User can pass "localhost; rm -rf /"
    command = f"ping -c 1 {target}"
    output = subprocess.check_output(command, shell=True)
    
    return output

@app.route('/upload', methods=['POST'])
def upload_config():
    if 'config' not in request.files:
        return "No file part", 400
    
    file = request.files['config']
    content = file.read()
    
    try:
        # A03: Insecure Deserialization (YAML)
        # yaml.load is unsafe by default in older versions or if Loader is not specified safely
        # Here we simulate the unsafe usage often caught by tools
        data = yaml.load(content, Loader=yaml.Loader)
        return jsonify({"status": "parsed", "data": data})
    except Exception as e:
        return str(e), 500

@app.route('/restore_session', methods=['POST'])
def restore_session():
    # A03: Insecure Deserialization (Pickle)
    session_data = request.data
    try:
        session = pickle.loads(session_data)
        return jsonify({"status": "restored", "user": session.get('user')})
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # A04: Security Misconfiguration (Debug Enabled)
    app.run(host='0.0.0.0', port=5000, debug=True)
