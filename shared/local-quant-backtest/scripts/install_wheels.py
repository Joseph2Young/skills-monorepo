#!/usr/bin/env python3
"""安装 4 个本地回测引擎 wheel 到当前 Python 环境，并 patch pandas 3.x 兼容 bug。

幂等：重复执行安全。用法:
    python scripts/install_wheels.py [python可执行文件]
不传参数时用当前解释器。"""
import glob
import importlib
import os
import subprocess
import sys
import xg_mom_backtrader  # noqa: F401  探测是否已装

WHEELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wheels")


def patch(pkg_dirname: str) -> int:
    """把 site-packages 里该包的 fillna(method='ffill') 替换为 .ffill()。返回 patch 数。"""
    import importlib
    mod = importlib.import_module(pkg_dirname)
    pkg_root = os.path.dirname(mod.__file__)
    n = 0
    for f in glob.glob(os.path.join(pkg_root, "*.py")):
        s = open(f, encoding="utf-8", errors="ignore").read()
        c = s.count(".fillna(method='ffill')")
        if c:
            open(f, "w", encoding="utf-8").write(s.replace(".fillna(method='ffill')", ".ffill()"))
            n += c
    return n


def main() -> None:
    wheels = sorted(glob.glob(os.path.join(WHEELS_DIR, "*.whl")))
    assert wheels, f"找不到 wheel: {WHEELS_DIR}"
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--force-reinstall", "--no-deps", *wheels])
    total = 0
    for pkg in ["xg_mom_backtrader", "xg_zcph_backtrader", "xg_rank_factor_backtrader", "xg_tdx_func"]:
        importlib.invalidate_caches()
        n = patch(pkg)
        total += n
        print(f"  {pkg}: patch {n} 处")
    print(f"完成：{len(wheels)} 个 wheel 已安装，共 patch {total} 处 pandas 3.x 兼容问题")


if __name__ == "__main__":
    main()
