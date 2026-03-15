import logging
import os
from unittest.mock import patch, MagicMock
from src.uPtt.app import setup_logging

def test_setup_logging_basic():
    # Clear existing handlers to test fresh setup
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    setup_logging(debug_mode=False)
    
    assert root_logger.level == logging.INFO
    # Should have at least one handler (console)
    assert len(root_logger.handlers) >= 1

def test_setup_logging_debug():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    if os.path.exists("uptt_debug.log"):
        os.remove("uptt_debug.log")
        
    try:
        setup_logging(debug_mode=True)
        assert root_logger.level == logging.DEBUG
        assert os.path.exists("uptt_debug.log")
    finally:
        if os.path.exists("uptt_debug.log"):
            os.remove("uptt_debug.log")
