import os
import uvicorn
from fastapi import FastAPI

from db.database import create_db_and_tables
from web_server.ai.router import router as query_router

app = FastAPI()
app.include_router(query_router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


if __name__ == '__main__':
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    uvicorn.run(app, host='0.0.0.0', port=13113)
