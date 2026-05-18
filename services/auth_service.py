import sqlite3
import hashlib
import os
import uuid
import base64
import re
import time

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "database", "attendance_system.db")

def generate_recovery_key():
    """Generates a secure, readable recovery key."""
    raw = uuid.uuid4().hex[:16].upper()
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}"

def is_valid_email(email: str) -> bool:
    """Basic regex validation for email."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))

def obfuscate_pwd(pwd: str) -> str:
    """Simple obfuscation so it's not plaintext in SQLite browser."""
    if not pwd: return ""
    return base64.b64encode(pwd.encode('utf-8')).decode('utf-8')

def deobfuscate_pwd(pwd: str) -> str:
    """Deobfuscates base64 back to plaintext."""
    if not pwd: return ""
    try:
        return base64.b64decode(pwd.encode('utf-8')).decode('utf-8')
    except Exception:
        return ""

def ensure_recovery_key_column():
    """Ensures the Teachers table has a recovery_key column."""
    db_path = get_db_path()
    if not os.path.exists(db_path): return
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(Teachers)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'recovery_key' not in columns:
                cursor.execute("ALTER TABLE Teachers ADD COLUMN recovery_key TEXT")
                
                # For existing Admin Teacher, generate a default key (or random)
                default_key = generate_recovery_key()
                cursor.execute("UPDATE Teachers SET recovery_key = ? WHERE teacher_id = 1", (default_key,))
                conn.commit()
    except Exception as e:
        print(f"Schema update error: {e}")

def ensure_gmail_app_password_column():
    """Ensures the Teachers table has a gmail_app_password column."""
    db_path = get_db_path()
    if not os.path.exists(db_path): return
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(Teachers)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'gmail_app_password' not in columns:
                cursor.execute("ALTER TABLE Teachers ADD COLUMN gmail_app_password TEXT")
                conn.commit()
    except Exception as e:
        print(f"Gmail schema update error: {e}")

# Run schema updates on import
ensure_recovery_key_column()
ensure_gmail_app_password_column()

def hash_password(password: str) -> str:
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# Memory dictionary for simple brute-force protection
_login_attempts = {}

def verify_login(email: str, password: str):
    """
    Verifies user credentials.
    Returns teacher data dict if successful, None otherwise.
    """
    # Brute-force protection: lock out after 5 failed attempts for 5 minutes
    current_time = time.time()
    if email in _login_attempts:
        attempts, lock_time = _login_attempts[email]
        if lock_time and current_time < lock_time:
            print("Brute-force lockout active.")
            return None # Locked out
        elif lock_time and current_time >= lock_time:
            _login_attempts[email] = [0, None] # Reset lock
            
    hashed_pwd = hash_password(password)
    
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT teacher_id, name, email, recovery_key
                FROM Teachers 
                WHERE email = ? AND password_hash = ?
            ''', (email, hashed_pwd))
            
            row = cursor.fetchone()
            if row:
                _login_attempts[email] = [0, None] # Success, reset attempts
                return {
                    "teacher_id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "recovery_key": row[3]
                }
            
            # Failed attempt
            if email not in _login_attempts:
                _login_attempts[email] = [1, None]
            else:
                _login_attempts[email][0] += 1
                if _login_attempts[email][0] >= 5:
                    _login_attempts[email][1] = current_time + 300 # Lock for 5 mins
                    print("Account locked due to 5 failed attempts.")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def register_teacher(name: str, email: str, password: str):
    """
    Registers a new teacher and generates a recovery key.
    Returns (True, recovery_key) if successful, (False, None) otherwise.
    """
    if not is_valid_email(email):
        return False, None

    hashed_pwd = hash_password(password)
    recovery_key = generate_recovery_key()
    
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            
            # Check if email exists
            cursor.execute("SELECT 1 FROM Teachers WHERE email = ?", (email,))
            if cursor.fetchone():
                return False, None  # Email already exists
                
            cursor.execute('''
                INSERT INTO Teachers (name, email, password_hash, recovery_key)
                VALUES (?, ?, ?, ?)
            ''', (name, email, hashed_pwd, recovery_key))
            conn.commit()
            return True, recovery_key
    except Exception as e:
        print(f"Registration error: {e}")
        return False, None

def reset_password_with_key(email: str, recovery_key: str, new_password: str) -> bool:
    """Resets password using email and recovery key."""
    hashed_pwd = hash_password(new_password)
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT teacher_id FROM Teachers WHERE email = ? AND recovery_key = ?", (email, recovery_key))
            row = cursor.fetchone()
            if row:
                teacher_id = row[0]
                cursor.execute("UPDATE Teachers SET password_hash = ? WHERE teacher_id = ?", (hashed_pwd, teacher_id))
                conn.commit()
                return True
            return False
    except Exception as e:
        print(f"Password reset error: {e}")
        return False

def update_teacher_profile(teacher_id: int, name: str, email: str, new_password: str = None, gmail_app_password: str = None) -> bool:
    """Updates the teacher's profile (name, email, password, and gmail_app_password)."""
    if not is_valid_email(email):
        return False

    enc_app_pwd = obfuscate_pwd(gmail_app_password)

    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            
            # Check if email is being changed and already exists for another teacher
            cursor.execute("SELECT teacher_id FROM Teachers WHERE email = ? AND teacher_id != ?", (email, teacher_id))
            if cursor.fetchone():
                return False # Email taken by someone else
            
            if new_password:
                hashed_pwd = hash_password(new_password)
                cursor.execute("UPDATE Teachers SET name = ?, email = ?, password_hash = ?, gmail_app_password = ? WHERE teacher_id = ?", 
                               (name, email, hashed_pwd, enc_app_pwd, teacher_id))
            else:
                cursor.execute("UPDATE Teachers SET name = ?, email = ?, gmail_app_password = ? WHERE teacher_id = ?", 
                               (name, email, enc_app_pwd, teacher_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Profile update error: {e}")
        return False

def get_teacher_details(teacher_id: int):
    """Fetches details including the recovery key and gmail app password for the dashboard."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, email, recovery_key, gmail_app_password FROM Teachers WHERE teacher_id = ?", (teacher_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "name": row[0],
                    "email": row[1],
                    "recovery_key": row[2],
                    "gmail_app_password": deobfuscate_pwd(row[3]) if row[3] else ""
                }
            return None
    except Exception as e:
        print(f"Get details error: {e}")
        return None
