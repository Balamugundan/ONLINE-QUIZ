import os
import hmac
import hashlib
import base64
import json
import time
from functools import wraps
from flask import request, jsonify
from werkzeug.security import check_password_hash
from database import admins_col, students_col

SECRET_KEY = os.getenv("SECRET_KEY", "super-secure-quiz-secret-key-9923847291").encode('utf-8')

def generate_token(payload_data, expires_in_seconds=86400):
    """Generates an HMAC-SHA256 signed tamper-proof token."""
    payload = dict(payload_data)
    payload["exp"] = int(time.time()) + expires_in_seconds
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    
    signature = hmac.new(SECRET_KEY, payload_b64.encode('utf-8'), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    
    return f"{payload_b64}.{sig_b64}"

def verify_token(token):
    """Verifies HMAC signature and expiration."""
    if not token or '.' not in token:
        return None
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        
        # Check signature
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode('utf-8'), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode('utf-8').rstrip('=')
        
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None
            
        # Add padding back if necessary
        pad = len(payload_b64) % 4
        if pad:
            payload_b64 += '=' * (4 - pad)
            
        payload_data = json.loads(base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8'))
        
        # Expiry check
        if payload_data.get("exp", 0) < time.time():
            return None
            
        return payload_data
    except Exception:
        return None

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif request.cookies.get("admin_token"):
            token = request.cookies.get("admin_token")
            
        if not token:
            return jsonify({"status": "error", "message": "Missing authorization token"}), 401
            
        payload = verify_token(token)
        if not payload or payload.get("role") != "admin":
            return jsonify({"status": "error", "message": "Invalid or expired admin token"}), 401
            
        return f(*args, **kwargs)
    return decorated

# In-memory sliding window for login rate limiting / brute-force protection
FAILED_LOGIN_ATTEMPTS = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes

def is_ip_rate_limited(ip):
    now = time.time()
    record = FAILED_LOGIN_ATTEMPTS.get(ip)
    if not record:
        return False, 0
    attempts, first_time = record
    if now - first_time > LOCKOUT_DURATION_SECONDS:
        del FAILED_LOGIN_ATTEMPTS[ip]
        return False, 0
    if attempts >= MAX_FAILED_ATTEMPTS:
        remaining = int(LOCKOUT_DURATION_SECONDS - (now - first_time))
        return True, max(1, remaining)
    return False, 0

def record_failed_login(ip):
    now = time.time()
    if ip not in FAILED_LOGIN_ATTEMPTS:
        FAILED_LOGIN_ATTEMPTS[ip] = (1, now)
    else:
        attempts, first_time = FAILED_LOGIN_ATTEMPTS[ip]
        if now - first_time > LOCKOUT_DURATION_SECONDS:
            FAILED_LOGIN_ATTEMPTS[ip] = (1, now)
        else:
            FAILED_LOGIN_ATTEMPTS[ip] = (attempts + 1, first_time)

def reset_failed_login(ip):
    if ip in FAILED_LOGIN_ATTEMPTS:
        del FAILED_LOGIN_ATTEMPTS[ip]

def authenticate_admin(username, password, client_ip="default"):
    """Authenticates admin credentials from DB with rate limiting."""
    is_limited, wait_secs = is_ip_rate_limited(client_ip)
    if is_limited:
        return {"error": f"Too many failed login attempts. Account temporarily locked. Try again in {wait_secs} seconds."}

    admin = admins_col.find_one({"username": username.strip()})
    if not admin or not check_password_hash(admin.get("password_hash", ""), password):
        record_failed_login(client_ip)
        return None

    reset_failed_login(client_ip)
    token = generate_token({"role": "admin", "username": admin["username"]})
    return {
        "username": admin["username"],
        "token": token
    }
