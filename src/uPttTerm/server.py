import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import PyPtt
from fastapi import FastAPI
from pydantic import BaseModel

from . import __name__ as pkg_name, __version__
from .ptt import UPttService

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
        ptt_service.close()
        print("已成功登出 PTT。")
    except Exception as e:
        print(f"登出 PTT 時發生錯誤: {e}")

app = FastAPI(lifespan=lifespan)

class LoginRequest(BaseModel):
    """登入請求的資料結構"""
    username: str
    password: str

class ApiCallRequest(BaseModel):
    """通用 API 呼叫的資料結構"""
    api: str
    args: Optional[Dict[str, Any]] = None


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
def call_api(api: str, args: str = None):
    if not api:
        return {"error": "API name is required."}

    json_args = None
    if args:
        try:
            json_args = json.loads(args)
        except json.JSONDecodeError as e:
            print(f"Invalid args: {args}")
            return {"error": f"Invalid args format: {e}"}

    print(api, json_args)
    try:
        result = ptt_service.call(api, json_args)
        return {"result": result}
    except Exception as e:
        return {"error": f"{e}"}
