import datetime
import threading

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi import applications
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi_pagination import add_pagination

from db.database import create_db_and_tables
from parser.parser_worker import init_process, process_exit
from tools.log_tools import manage_logger as logger
from web_server.ai.router import router as ai_router
from web_server.dify.router import router as dify_router


def swagger_monkey_patch(*args, **kwargs):
    """
    Wrap the function which is generating the HTML for the /docs endpoint and
    overwrite the default values for the swagger js and css.
    """

    return get_swagger_ui_html(
        *args, **kwargs,
        swagger_js_url="https://cdn.staticfile.org/swagger-ui/5.2.0/swagger-ui-bundle.min.js",
        swagger_css_url="https://cdn.staticfile.org/swagger-ui/5.2.0/swagger-ui.min.css")


applications.get_swagger_ui_html = swagger_monkey_patch

app = FastAPI()
add_pagination(app)
app.include_router(ai_router)
app.include_router(dify_router)

origins = [
    '*'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request(request: Request, call_next):
    # 记录开始时间和请求信息
    start_time = datetime.datetime.now()
    path = request.url.path
    query_params = dict(request.query_params)  # 获取查询参数

    # 打印开始日志
    logger.debug(f'请求路径: {path} | 参数: {query_params}')

    try:
        response = await call_next(request)
    finally:
        # 确保无论是否异常都记录结束时间
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logger.debug(f'请求时长: {duration.total_seconds():.2f}s')

    return response


if __name__ == '__main__':
    load_dotenv()
    # 初始化数据库
    create_db_and_tables()
    # 启动预处理流程
    threading.Thread(target=init_process, daemon=True).start()
    uvicorn.run(
        app='main:app',
        host='0.0.0.0',
        port=13113,
        timeout_keep_alive=3,  # 指定3s内保持活动状态的连接
        backlog=4096  # 等待处理最大连接数
    )
    # 预处理退出流程
    process_exit()
