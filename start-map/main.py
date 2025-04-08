import uvicorn
from fastapi import FastAPI
from web_server.routers.ai_router import router as query_router

app = FastAPI()
app.include_router(query_router)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=13113)
