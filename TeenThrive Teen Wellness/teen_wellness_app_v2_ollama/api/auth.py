import time, jwt
from passlib.context import CryptContext
from typing import Optional

JWT_SECRET = "dev-secret-change-me"
JWT_ALG = "HS256"
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p:str)->str: return pwd.hash(p)
def verify_password(p, h)->bool: return pwd.verify(p, h)

def create_token(sub:str, exp:int=60*60*24):
    payload = {"sub":sub, "exp":int(time.time())+exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token:str)->Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None