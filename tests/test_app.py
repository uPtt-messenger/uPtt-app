import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.getcwd())

from src.uPttTerm.app import UPttApp


def test_app_initialization():
    app = UPttApp()

    assert app is not None
    assert isinstance(app, UPttApp)