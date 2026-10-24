"""Shared pytest fixtures/config.

Provides a dummy OPENAI_API_KEY so provider constructors (which build API
clients in `__init__`, not at import time) don't need a real key for offline
unit tests.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-not-used")
