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

def authenticate_admin(username, password):
    """Authenticates admin credentials from DB."""
    admin = admins_col.find_one({"username": username.strip()})
    if not admin:
        return None
    if check_password_hash(admin.get("password_hash", ""), password):
        token = generate_token({"role": "admin", "username": admin["username"]})
        return {
            "username": admin["username"],
            "token": token
        }
    return None
