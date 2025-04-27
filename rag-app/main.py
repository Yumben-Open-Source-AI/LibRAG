import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

from db.database import create_db_and_tables
from web_server.ai.router import router as query_router

app = FastAPI()
app.include_router(query_router)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


if __name__ == '__main__':
    load_dotenv()
    uvicorn.run(app, host='0.0.0.0', port=13113)
