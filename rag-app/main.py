import datetime
import uvicorn
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from db.database import create_db_and_tables
from fastapi.middleware.cors import CORSMiddleware
from web_server.ai.router import router as ai_router
from web_server.dify.router import router as dify_router
from tools.log_tools import manage_logger as logger
from multiprocessing import cpu_count

app = FastAPI()
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


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


if __name__ == '__main__':
    load_dotenv()
    uvicorn.run(
        app='main:app',
        host='0.0.0.0',
        port=13113,
        workers=cpu_count() * 2,
        timeout_keep_alive=3,  # 指定3s内保持活动状态的连接
        backlog=4096  # 等待处理最大连接数
    )
