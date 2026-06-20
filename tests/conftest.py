"""Shared pytest setup.

Set ODR_DISABLE_BACKGROUND before web_app is imported so importing it does not
spawn the watchdog thread or run startup cleanup (which would race tests and
touch the real session DB). Also point ODR_DB_PATH at a throwaway file as a
safety net for the module-import-time init_db() call.
"""

import os
import tempfile

os.environ.setdefault("ODR_DISABLE_BACKGROUND", "1")
os.environ.setdefault(
    "ODR_DB_PATH", os.path.join(tempfile.gettempdir(), "odr_test_import.db")
)
