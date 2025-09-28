from contextlib import asynccontextmanager

import PyPtt
from fastapi import FastAPI

from . import __name__ as pkg_name, __version__
from .ptt import UPttService

app = FastAPI()

ptt_service = UPttService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在應用程式啟動時執行的程式碼 (yield 之前)
    print("應用程式啟動，PTT Service 已準備就緒。")

    yield  # 應用程式在此運行

    # 在應用程式關閉時執行的程式碼 (yield 之後)
    print("應用程式正在關閉，準備登出 PTT...")
    try:
        # 假設您的服務有一個 logout 方法來清理和登出
        ptt_service.call('logout')
        print("已成功登出 PTT。")
    except Exception as e:
        print(f"登出 PTT 時發生錯誤: {e}")


@app.get("/health")
def health_check():
    """一個簡單的健康檢查端點，用於確認伺服器是否正常回應。"""
    return {"status": "ok"}


@app.get("/")
def home():
    return {"message": f"Hello from {pkg_name} v{__version__}."}


@app.get("/api/login")
def login(username: str, password: str):
    if not username or not password:
        return {"error": "Username and password are required."}
    try:
        ptt_service.login(username, password)
        return {"result": "Login successful."}
    except PyPtt.Error as e:
        return {"error": f"{e}"}


@app.get("/api/call")
def call_api(api: str, args: dict = None):
    if not api:
        return {"error": "API name is required."}
    try:
        result = ptt_service.call(api, args)
        return {"result": result}
    except PyPtt.Error as e:
        return {"error": f"{e}"}
