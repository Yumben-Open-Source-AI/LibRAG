import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

from db.database import create_db_and_tables
from fastapi.middleware.cors import CORSMiddleware
from web_server.ai.router import router as query_router

app = FastAPI()
app.include_router(query_router)

origins = [
    'http://localhost:5173'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


if __name__ == '__main__':
    load_dotenv()
    uvicorn.run(app, host='0.0.0.0', port=13113)
