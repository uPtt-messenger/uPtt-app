import os
import sys
from unittest.mock import MagicMock

sys.path.append(os.getcwd())

from src.uPttTerm.app import UPttApp


def test_app_initialization():
    # Mock the PyPtt.Service dependency
    mock_ptt_service = MagicMock()

    # Instantiate UPttApp with the mock service
    app = UPttApp(mock_ptt_service)

    assert app is not None
    assert isinstance(app, UPttApp)
    assert app.ptt_service == mock_ptt_service
