import os.path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlmodel import Session, SQLModel

sqlite_name = 'librag.db'
sqlite_path = os.path.join(os.path.dirname(__file__), sqlite_name)
sqlite_url = f"sqlite:///{sqlite_path}?charset=utf8"

connect_args = {'check_same_thread': False}
engine = create_engine(
    sqlite_url,
    connect_args=connect_args,
    pool_size=30,  # 进程池大小
    max_overflow=20,  # 额外连接数
    pool_timeout=30,  # 等待连接超时时间
    pool_recycle=300,  # 5分钟回收连接避免超时
    pool_pre_ping=True,  # 执行前检查连接活性
)


@event.listens_for(engine, 'connect')
def sqlite_connect(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA wal_autocheckpoint=100')
    finally:
        cursor.close()


def get_session():
    with Session(engine) as session:
        yield session


def get_engine():
    return engine


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


SessionDep = Annotated[Session, Depends(get_session)]
