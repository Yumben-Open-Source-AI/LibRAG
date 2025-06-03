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
    pool_size=30,
    pool_timeout=30,
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
