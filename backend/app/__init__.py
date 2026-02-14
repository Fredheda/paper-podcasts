"""Backend FastAPI package.

Import config on package load so repository path bootstrap happens before any
submodule tries to import shared modules from `src.*`.
"""

# Ensures REPO_ROOT is added to sys.path as early as possible.
from . import config as _config
