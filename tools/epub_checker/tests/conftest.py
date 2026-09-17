"""epub_checker 测试的共享 fixture。"""
import sys
from pathlib import Path

# 让 pytest 能 import epub_checker，无需安装
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
