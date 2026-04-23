#
# Copyright (c) 2026 Sergio DuBois (sentientsergio@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/paperlint
#

"""Pytest bootstrap: ensure repo root is on ``sys.path`` before imports.

``paperlint.extract`` imports the vendored ``tomd`` package from the sibling
``tomd/`` directory. Without ``pip install -e ./tomd``, Python still finds it
when the repository root is on ``sys.path``. ``[tool.pytest.ini_options]``
``pythonpath`` does the same for recent pytest; this file covers older pytest
or non-standard invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_root = str(_REPO_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)
