import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())

from src.uPttTerm.app import UPttApp


def test_app_initialization():
    with patch('src.uPttTerm.app.UPttService') as MockUPttService:
        mock_service_instance = MagicMock()
        MockUPttService.return_value = mock_service_instance
        app = UPttApp()

        assert app is not None
        assert isinstance(app, UPttApp)
        assert app.ptt_service == mock_service_instance