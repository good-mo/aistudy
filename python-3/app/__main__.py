"""
app.__main__ —— 使 `python -m app` 可直接执行

将命令行入口委托给 app.cli.main.main()，
从而支持 `python -m app <command>` 的用法。
"""

from __future__ import annotations

import sys

from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
