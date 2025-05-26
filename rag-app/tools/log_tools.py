# simple_log.py
import logging, os, sys, inspect
from pathlib import Path


def setup(log_dir="./logs", level=logging.INFO):
    """
    初始化简单日志系统：
      • 终端 + 文件双输出
      • 自动创建目录
      • 默认 INFO 级别，可改 DEBUG/ERROR 等
      # # ---- 方式 A：显式用 log() --------------------------------------------------
      # log("服务启动 OK")
      # log("调试变量:", {"x": 10}, level="debug")
      # log("发生异常!", level="error")
      #
      # # ---- 方式 B：一键把所有 print 劫持成日志 ------------------------------------
      # hijack_print()
      # print("这行其实写进日志了")
      # print("支持", "多个参数", 123)
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname).1s] %(filename)s:%(lineno)d | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_dir, "app.log"),
                                encoding="utf-8"),
        ],
    )


def log(*objects,
        sep=" ",
        end="\n",
        level="info",
        stacklevel=1):
    """
    像 print 一样使用：
        log("hello", 123)
        log("warn msg", level="warning")
    """
    msg = sep.join(map(str, objects)) + end.rstrip("\n")
    # 取调用方(原 print 所在行) 的堆栈位置
    getattr(logging, level.lower(), logging.info)(
        msg,
        stacklevel=stacklevel + 1  # 向上再跳一层
    )


def hijack_print():
    """把内置 print 替换成 log，调用处不用改任何代码"""
    import builtins
    builtins.print = lambda *a, **kw: log(*a, **kw, stacklevel=2)
