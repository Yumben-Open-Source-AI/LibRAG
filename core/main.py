import datetime
import threading

import uvicorn
from dotenv import load_dotenv
from fastapi import Request, applications
from fastapi import FastAPI as FastAPIBase
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi_pagination import add_pagination
from starlette.staticfiles import StaticFiles

from db.database import create_db_and_tables
from parser.parser_worker import init_process, process_exit
from tools.log_tools import manage_logger as logger
from web_server.ai.router import router as ai_router
from web_server.dify.router import router as dify_router


class FastAPI(FastAPIBase):
    def __init__(self, *args, **kwargs) -> None:
        # 排除默认js & css
        if "swagger_js_url" in kwargs:
            self.swagger_js_url = kwargs.pop("swagger_js_url")
        if "swagger_css_url" in kwargs:
            self.swagger_css_url = kwargs.pop("swagger_css_url")

        def get_swagger_ui_html_with_local(*args, **kwargs):
            return get_swagger_ui_html(
                *args,
                **kwargs,
                swagger_js_url=self.swagger_js_url,
                swagger_css_url=self.swagger_css_url,
            )

        applications.get_swagger_ui_html = get_swagger_ui_html_with_local
        super(FastAPI, self).__init__(*args, **kwargs)


app = FastAPI(
    title="LibRAG API",
    swagger_js_url="/static/swagger-ui/swagger-ui-bundle.min.js",
    swagger_css_url="/static/swagger-ui/swagger-ui.min.css",
    docs_url=None,
    redoc_url=None
)
add_pagination(app)
app.include_router(ai_router)
app.include_router(dify_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    logger.info(f'请求路径: {path} | 参数: {query_params}')

    try:
        response = await call_next(request)
    finally:
        # 确保无论是否异常都记录结束时间
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logger.info(f'请求时长: {duration.total_seconds():.2f}s')

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
        workers=10,
        timeout_keep_alive=3,  # 指定3s内保持活动状态的连接
        backlog=4096  # 等待处理最大连接数
    )
    # 预处理退出流程
    process_exit()
