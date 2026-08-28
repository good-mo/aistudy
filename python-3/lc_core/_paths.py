"""lc_core._paths —— 内部路径工具。

计算各子包复用原 lc/ 脚本所需的源目录路径。
"""

import os
import sys

# 包根目录：/workspace/lc_core
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
# 项目根目录：/workspace
_PROJECT_ROOT = os.path.dirname(_PKG_DIR)
# 原脚本目录：/workspace/lc
LC_SRC_DIR = os.path.join(_PROJECT_ROOT, "lc")


def ensure_source_on_path() -> None:
    """确保原 lc/ 脚本目录在 sys.path 上，便于复用其逻辑。"""
    if LC_SRC_DIR not in sys.path:
        sys.path.insert(0, LC_SRC_DIR)
