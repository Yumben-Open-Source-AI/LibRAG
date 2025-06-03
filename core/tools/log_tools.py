import os

import logging
from logging.handlers import TimedRotatingFileHandler

FATAL = CRITICAL = 50
ERROR = 40
WARN = WARNING = 30
INFO = 20
DEBUG = 10
NOTSET = 0

_nameToLevel = {
    'CRITICAL': CRITICAL,
    'FATAL': FATAL,
    'ERROR': ERROR,
    'WARN': WARNING,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
    'NOTSET': NOTSET,
}

_home_dir = './logs'
_datefmt = '%Y-%m-%d %H:%M:%S'
_formatter = '%(asctime)s 文件名[%(filename)s] 函数名[%(funcName)s] 行数[%(lineno)d] [%(levelname)s]---%(message)s'


class Logger:
    """
    logger 日志记录
    """

    def __init__(self, log_name: str, level: str):
        os.makedirs(_home_dir, exist_ok=True)
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(_nameToLevel[level])
        self.logger.addHandler(self.get_time_handler(log_name))
        self.logger.addHandler(self.get_stream_handler())

    @staticmethod
    def get_time_handler(log_name: str):
        """ 日志处理器 日志切割轮转按天切割 """
        time_handler = TimedRotatingFileHandler(
            f'{_home_dir}/{log_name}.log',
            when='D',
            backupCount=7,
            encoding="utf-8"
        )
        time_format = logging.Formatter(_formatter, datefmt=_datefmt)
        time_handler.setFormatter(time_format)
        return time_handler

    @staticmethod
    def get_stream_handler():
        """ 控制台输出处理器 """
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(_formatter, datefmt=_datefmt)
        console_handler.setFormatter(console_formatter)
        return console_handler


# 解析器日志
parser_logger = Logger('parser', 'DEBUG').logger
# 选择器日志
selector_logger = Logger('selector', 'DEBUG').logger
# 管理部分日志
manage_logger = Logger('manage', 'DEBUG').logger
