"""
@Project ：core 
@File    ：create_user.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/6/5 上午10:42 
"""
from db.database import get_session
from web_server.ai.models import User
from web_server.ai.views import get_pwd_hash


def create_user(**kwargs):
    session = next(get_session())
    kwargs['hashed_password'] = get_pwd_hash(kwargs['password'])
    session.add(User(**kwargs))
    session.commit()


if __name__ == '__main__':
    user_name = input('username:')
    password = input('password:')
    create_user(user_name=user_name, password=password)
