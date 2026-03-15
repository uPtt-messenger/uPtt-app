import json
import asyncio
import time
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Set

import PyPtt
from fastapi import FastAPI
from pydantic import BaseModel

from uPtt import __name__ as pkg_name, __version__
from .ptt import UPttService
from .utils import HOUR

ptt_service = UPttService()
last_request_time = time.time()
active_clients: Set[str] = set()
shutdown_task: Optional[asyncio.Task] = None

# 閒置逾時
IDLE_TIMEOUT = 24 * HOUR

def log_server(message):
    """將伺服器訊息寫入 log 檔"""
    try:
        log_path = os.path.expanduser("~/uPtt_server.log")
        with open(log_path, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass

def force_exit():
    """強制結束行程。"""
    log_server("執行 force_exit，結束行程。")
    os._exit(0)

async def idle_monitor():
    """定期檢查伺服器是否閒置過久。"""

    # active_clients
    while True:
        await asyncio.sleep(2)
        now = time.time()
        # 情況 A：真的沒活動視窗且超過 2 秒
        if len(active_clients) == 0 and now - last_request_time > 1:
            if not shutdown_task or shutdown_task.done():
                log_server("Idle monitor: 無活動視窗，觸發關閉。")
                await shutdown_server()
        # 情況 B：超過 IDLE_TIMEOUT
        elif now - last_request_time > IDLE_TIMEOUT:
            log_server("Idle monitor: 超過閒置上限，觸發關閉。")
            await shutdown_server()

async def shutdown_server():
    """快速登出並結束伺服器。"""
    global shutdown_task
    log_server("開始執行 shutdown_server...")
    try:
        ptt_service.call('logout')
        ptt_service.close()
        log_server("PTT 登出與服務關閉完成。")
    except Exception as e:
        log_server(f"PTT 登出失敗: {e}")
    
    threading.Timer(0.2, force_exit).start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_server("伺服器 Lifespan 啟動。")
    monitor_task = asyncio.create_task(idle_monitor())
    yield 
    log_server("伺服器 Lifespan 結束。")
    monitor_task.cancel()

app = FastAPI(lifespan=lifespan)

def update_last_request():
    global last_request_time, shutdown_task
    last_request_time = time.time()
    
    # 只要有任何請求，且目前有「待命關閉任務」，就取消它
    if shutdown_task and not shutdown_task.done():
        # 注意：在執行緒環境中取消 asyncio 任務需要小心
        # 這裡我們是在主執行緒中處理 FastAPI 請求
        log_server("偵測到活動，延後/取消關閉任務。")
        shutdown_task.cancel()
        shutdown_task = None

@app.get("/")
async def home():
    update_last_request()
    return {"message": f"Hello from {pkg_name} v{__version__}.", "active_clients": list(active_clients)}

@app.get("/api/register")
async def register(client_id: str):
    update_last_request()
    active_clients.add(client_id)
    log_server(f"視窗註冊: {client_id}, 目前總數: {len(active_clients)}")
    return {"result": "Registered", "active_count": len(active_clients)}

@app.get("/api/unregister")
async def unregister(client_id: str):
    update_last_request()
    if client_id in active_clients:
        active_clients.remove(client_id)
        log_server(f"視窗註銷: {client_id}, 目前剩餘: {len(active_clients)}")
    
    count = len(active_clients)
    if count == 0:
        global shutdown_task
        log_server("最後一個視窗已離開，排定 1 秒後關閉。")
        
        async def delayed_shutdown():
            try:
                await asyncio.sleep(1.0) # 給予 1 秒緩衝
                await shutdown_server()
            except asyncio.CancelledError:
                pass
            
        shutdown_task = asyncio.create_task(delayed_shutdown())
        
    return {"result": "Unregistered", "remaining_count": count}

@app.get("/api/login")
async def login(username: str, password: str):
    update_last_request()
    log_server(f"收到登入請求: {username}")
    try:
        ptt_service.login(username, password)
        return {"result": "Login successful."}
    except PyPtt.Error as e:
        return {"error": f"{e}"}

@app.get("/api/call")
async def call_api(api: str, args: str = None):
    update_last_request()
    if not api:
        return {"error": "API name is required."}

    # 搜尋請求不需要列印詳細日誌以免洗版
    if api != 'search_user':
        log_server(f"API Call: {api}")

    json_args = None
    if args:
        try:
            json_args = json.loads(args)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid args format: {e}"}

    try:
        if api == 'logout':
            active_clients.clear()
            
        result = ptt_service.call(api, json_args)
        
        if api == 'logout':
            asyncio.create_task(shutdown_server())
            
        return {"result": result}
    except Exception as e:
        return {"error": f"{e}"}

def run_server(host: str, port: int):
    import uvicorn
    log_server(f"Uvicorn 啟動於 {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="critical")

if __name__ == "__main__":
    import sys
    run_server("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
