import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import PyPtt
from fastapi import FastAPI
from pydantic import BaseModel

from uPttTerm import __name__ as pkg_name, __version__
from uPttTerm.ptt import UPttService

ptt_service = UPttService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在應用程式啟動時執行的程式碼 (yield 之前)
    yield  # 應用程式在此運行

    # 在應用程式關閉時執行的程式碼 (yield 之後)
    try:
        # 假設您的服務有一個 logout 方法來清理和登出
        ptt_service.call('logout')
        ptt_service.close()
    except Exception:
        pass

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
            return {"error": f"Invalid args format: {e}"}

    try:
        result = ptt_service.call(api, json_args)
        return {"result": result}
    except Exception as e:
        return {"error": f"{e}"}


def run_server(host: str, port: int):
    import uvicorn
    # 使用 critical 等級日誌，徹底讓伺服器安靜
    uvicorn.run(app, host=host, port=port, log_level="critical")

if __name__ == "__main__":
    import sys
    run_server("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
