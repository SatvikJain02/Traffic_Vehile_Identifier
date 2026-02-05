# datetime: To calculate when the token expires (e.g., 30 mins from now).
# timezone: To ensure we use universal time (UTC), not local time.
from datetime import datetime, timedelta, timezone
# Optional: Just a helper for typing (saying "this variable might be None").
from typing import Optional
# jwt: The library that creates the JWT (JSON Web Token).
# We need to install this: pip install pyjwt
import jwt 
# HTTPException: To send errors like "401 Unauthorized" (Go away!).
# Security/HTTPBearer: The "Guard" that checks for the token in the header.
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# --- 1. CONFIGURATION (The Settings) ---
# The Secret Key is used to "sign" the token. 
# If a hacker changes the token, the signature won't match this key, and we'll know.
SECRET_KEY = 'super_secret_diabolical_key'
ALGORITHM = 'HS256' # The math used to scramble the token.
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # VIP badge is valid for 30 mins.

# The "Bouncer" at the door (professionally: "Dependency Injection"). It expects a header like: "Authorization: Bearer <token>"
security = HTTPBearer()

# --- 2. FAKE DATABASE ---
# In real life, this would be a SQL database.
# Here, it's just a Python dictionary in memory.
# WARNING: If we restart the server, this gets wiped clean!
fake_users_db = {
    'admin': {
        'username': 'admin',
        'password': 'secretpassword',
        'disabled': False
    }
}

# --- 3. DATA MODELS (Pydantic) ---
# These ensure the data sent by the user is structured correctly.
# Writing Base model inside the brackets ensures that we are using Pydantic instead of traditional __init__ way.
class UserAuth(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str # The actual VIP badge string
    token_type: str   # Usually "JWT Bearer"
    expires_in: int   # Seconds until it dies

# --- 4. UTILITY FUNCTIONS (The Worker Bees) ---

# FUNCTION A: Create the Token (The Badge Maker)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    # Make a copy of the data so we don't accidentally change the original
    to_encode = data.copy()
    
    # Calculate "Death Time" for the token
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default to 15 mins if no time specified
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    # Add the expiration time ('exp') to the data inside the token
    to_encode.update({"exp": expire})
    
    # SCRAMBLE IT! Use the SECRET_KEY to turn the data into a long string.
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

# FUNCTION B: Verify the Token (The ID Checker)
# This function is used by 'Depends'. It runs before the endpoint logic.
def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    # 1. Extract the token string from the request header
    token = credentials.credentials
    
    try:
        # 2. Decode it. If the SECRET_KEY doesn't match, this crashes.
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 3. Get the username ('sub' stands for subject) from the token
        username: str = payload.get('sub')
        
        if username is None:
            raise HTTPException(status_code=401, detail="Token is missing username")
            
        return username # Pass the username to the endpoint
        
    except jwt.ExpiredSignatureError:
        # Token is too old
        raise HTTPException(status_code=401, detail="Token has expired! Login again.")
    except jwt.PyJWTError:
        # Token is fake or broken
        raise HTTPException(status_code=401, detail="Invalid token")

# --- 5. AUTH FUNCTIONS ---

# Registers a new user into our dictionary
def register_new_user(user: UserAuth):
    if user.username in fake_users_db:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # WARNING: In production, NEVER store plain passwords. Use Hashing!
    fake_users_db[user.username] = {
        'username': user.username,
        'password': user.password,  # Ideally: hash_password(user.password)
        'disabled': False
    }
    return user

# Checks if username exists AND password matches
def authenticate_user(user: UserAuth):
    db_user = fake_users_db.get(user.username)
    if not db_user:
        return None # User not found
    if db_user['password'] != user.password:
        return None # Wrong password
    return db_user