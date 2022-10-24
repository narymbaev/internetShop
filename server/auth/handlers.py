from jwt import decode, encode, exceptions
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

SECRET_KEY = 'fd3f59ea06e041498613d81e5b9438f5'


def token_response(token: str):
    return {'access token': token}

def signJWT(userID: int):
    payload = {'user_id': userID, 'exp': datetime.utcnow()+timedelta(seconds=10)}
    token = encode(payload, SECRET_KEY)
    return token

def decodeJWT(token: str):
    return decode(token, SECRET_KEY, algorithms='HS256')


# def hash_password(password: str):
#     return {}

def check_password(hashed_password: str, password: str):
    return check_password_hash(hashed_password, password)
