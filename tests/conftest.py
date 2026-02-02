import sys
from types import ModuleType
from unittest.mock import MagicMock

# Prevent src.db.__init__ from importing the real connection module
# which requires a live database driver at import time.
_fake_connection = ModuleType("src.db.connection")
_fake_connection.get_db = MagicMock()
_fake_connection.engine = MagicMock()
sys.modules["src.db.connection"] = _fake_connection
