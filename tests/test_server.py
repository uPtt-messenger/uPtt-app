import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

from src.uPtt.server import app, ptt_service

client = TestClient(app)

def test_home_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Hello from uPtt" in response.json()["message"]

def test_register_unregister():
    client_id = "test_client_1"
    
    # Register
    response = client.get(f"/api/register?client_id={client_id}")
    assert response.status_code == 200
    assert response.json()["result"] == "Registered"
    assert response.json()["active_count"] == 1
    
    # Unregister
    response = client.get(f"/api/unregister?client_id={client_id}")
    assert response.status_code == 200
    assert response.json()["result"] == "Unregistered"
    assert response.json()["remaining_count"] == 0

@patch("src.uPtt.server.ptt_service.login")
def test_login_endpoint(mock_login):
    mock_login.return_value = True
    response = client.get("/api/login?username=testuser&password=testpassword")
    assert response.status_code == 200
    assert response.json()["result"] == "Login successful."
    mock_login.assert_called_once_with("testuser", "testpassword")

@patch("src.uPtt.server.ptt_service.call")
def test_call_endpoint_success(mock_call):
    mock_call.return_value = {"some": "data"}
    args = json.dumps({"param": "value"})
    response = client.get(f"/api/call?api=some_api&args={args}")
    assert response.status_code == 200
    assert response.json()["result"] == {"some": "data"}
    mock_call.assert_called_once_with("some_api", {"param": "value"})

@patch("src.uPtt.server.ptt_service.call")
def test_call_endpoint_no_args(mock_call):
    mock_call.return_value = "ok"
    response = client.get("/api/call?api=ping")
    assert response.status_code == 200
    assert response.json()["result"] == "ok"
    mock_call.assert_called_once_with("ping", None)

def test_call_endpoint_missing_api():
    response = client.get("/api/call")
    # FastAPI will return 422 if required param 'api' is missing
    assert response.status_code == 422

def test_call_endpoint_invalid_json():
    response = client.get("/api/call?api=test&args=invalid_json")
    assert response.status_code == 200
    assert "error" in response.json()
    assert "Invalid args format" in response.json()["error"]
