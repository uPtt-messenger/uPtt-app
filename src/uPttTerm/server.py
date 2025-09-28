
from fastapi import FastAPI
import time

from . import __name__ as pkg_name, __version__

app = FastAPI()

@app.get("/health")
def health_check():
    """一個簡單的健康檢查端點，用於確認伺服器是否正常回應。"""
    return {"status": "ok"}

@app.get("/")
def home():
    return {"message": f"Hello from {pkg_name} v{__version__}!"}