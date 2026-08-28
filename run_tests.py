"""零依赖测试运行器(无需 pip 安装 pytest,离线可用)。

发现 tests/ 下所有 test_*.py,运行其中的 test_* 函数,报告通过/失败。
用法:
    python run_tests.py            # 用系统 Python(任意 3.11+)
    "…/Maya2025/bin/mayapy.exe" run_tests.py   # 用 mayapy 跑(同样只测纯逻辑层)

已安装 pytest 时,直接 `pytest` 亦可,效果一致。
"""

from __future__ import annotations

import importlib
import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    tests_dir = os.path.join(_ROOT, "tests")
    modules = [
        f"tests.{fn[:-3]}"
        for fn in sorted(os.listdir(tests_dir))
        if fn.startswith("test_") and fn.endswith(".py")
    ]

    passed = failed = 0
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
                print(f"PASS {mod_name}.{name}")
            except Exception:
                failed += 1
                print(f"FAIL {mod_name}.{name}")
                traceback.print_exc()

    print(f"\n--- {passed} passed, {failed} failed ---")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
