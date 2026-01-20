import json
import bcrypt
from pathlib import Path
from typing import Dict, Optional, List

# File to store users
USERS_DB_FILE = Path(__file__).parent / "users.json"

def _load_users() -> Dict:
    if not USERS_DB_FILE.exists():
        # Create default admin user if file doesn't exist
        # Password: 1234
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw("1234".encode('utf-8'), salt).decode('utf-8')
        default_db = {
            "admin": {
                "password": hashed,
                "is_admin": True
            }
        }
        _save_users(default_db)
        return default_db
    
    try:
        return json.loads(USERS_DB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_users(users: Dict):
    USERS_DB_FILE.write_text(json.dumps(users, indent=4), encoding="utf-8")

def authenticate(username: str, password: str) -> Optional[Dict]:
    """
    Returns user info (dict) if valid, None otherwise.
    User info includes 'is_admin'.
    """
    users = _load_users()
    user = users.get(username)
    
    if not user:
        return None
    
    stored_hash = user.get("password")
    if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return {"username": username, "is_admin": user.get("is_admin", False)}
    
    return None

def create_user(username: str, password: str, is_admin: bool = False) -> bool:
    """
    Creates a new user. Returns True if successful, False if user already exists.
    """
    users = _load_users()
    if username in users:
        return False
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    users[username] = {
        "password": hashed,
        "is_admin": is_admin
    }
    _save_users(users)
    return True

def list_users() -> List[Dict]:
    users = _load_users()
    return [{"username": k, "is_admin": v.get("is_admin", False)} for k, v in users.items()]

def delete_user(username: str) -> bool:
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False

# Initialize the DB on import if not exists
_load_users()
