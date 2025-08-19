"""
@Project ：core 
@File    ：views.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/6/9 上午10:08 
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from jwt import encode, decode
from fastapi import Depends, HTTPException, status, UploadFile
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from passlib.context import CryptContext
from sqlmodel import select

from db.database import SessionDep
from web_server.ai.models import User, ProcessingTask, Document
from web_server.ai.schemas import UserTokenConfig, TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/ai/token")


def verify_token(token: str = Depends(oauth2_scheme)):
    """验证token并检查过期时间"""
    api_keys = set(os.getenv('VALID_API_KEYS').split(','))
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, UserTokenConfig.get_secret_key(), algorithms=[UserTokenConfig.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        return TokenData(username=username)
    except ExpiredSignatureError:
        pass
    except InvalidTokenError:
        pass

    if token in api_keys:
        return

    raise credentials_exception


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_pwd_hash(pwd):
    return pwd_context.hash(pwd)


def get_user(db, username: str):
    return db.query(User).filter(User.user_name == username).first()


def authenticate_user(db: SessionDep, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, UserTokenConfig.get_secret_key(), algorithm=UserTokenConfig.ALGORITHM)
    return encoded_jwt


def get_current_user(db: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, UserTokenConfig.get_secret_key(), algorithms=[UserTokenConfig.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


def check_file_md5(file: UploadFile, session: SessionDep, chunk_size: int = 8192) -> tuple[ProcessingTask, str]:
    """计算上传文件的 MD5 哈希值"""
    import hashlib
    md5 = hashlib.md5()
    file.file.seek(0)
    while chunk := file.file.read(chunk_size):
        md5.update(chunk)
    file.file.seek(0)
    file_md5 = md5.hexdigest()
    query = session.query(ProcessingTask).filter_by(file_size=file.size, file_md5=file_md5)
    db_file = query.first()
    return db_file, file_md5


def check_file_strategy(file: UploadFile, session: SessionDep, kb_id: int, strategy: str):
    """ 校验上传文件的 策略重复性"""
    filename = file.filename
    # 相同文件相同切割策略不允许上传
    statement = select(Document).where(
        Document.file_path.like(f"%{filename}%"),
        Document.parse_strategy == strategy,
        Document.kb_id == kb_id
    )
    db_strategies = session.exec(statement).all()
    statement = select(ProcessingTask).where(
        ProcessingTask.file_path.like(f"%{filename}%"),
        ProcessingTask.parse_strategy == strategy,
        ProcessingTask.kb_id == kb_id,
        ProcessingTask.status != 'filing'
    )
    db_tasks = session.exec(statement).all()
    return len(db_strategies) > 0 or len(db_tasks) > 0
