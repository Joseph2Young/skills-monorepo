#!/usr/bin/env python3
"""
重复文件检测：按文件大小分组，同尺寸组内计算 MD5，找出内容完全相同的文件。

用法：
    python3 find_duplicates.py [目录...] [--min-mb 0.5] [--top 30]

默认扫描 ~/Downloads ~/Desktop ~/Documents，最小 512 KB，输出前 25 组。

注意：重复 ≠ 多余。各项目 images/ 下的同名资源、正式公文的版本对照副本、
程序依赖库的多路径副本，都不应删除。只有渲染管线中间产物
（sources/*_files/、validation/readback_files/）是安全的清理对象。
"""
import os
import sys
import hashlib
import argparse
import collections

DEFAULT_ROOTS = ["~/Downloads", "~/Desktop", "~/Documents"]
SKIP_DIR_NAMES = {".git", "node_modules", ".Trash", "Library"}


def iter_files(roots, min_bytes):
    by_size = collections.defaultdict(list)
    for root in roots:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # 剪枝：跳过无关的大目录
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    if os.path.islink(path):
                        continue
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if size >= min_bytes:
                    by_size[size].append(path)
    return by_size


def md5_of(path, chunk=1 << 20):
    h = hashlib.md5()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(chunk), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def find_duplicates(roots, min_bytes):
    by_size = iter_files(roots, min_bytes)
    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue  # 尺寸唯一，不可能是重复
        by_hash = collections.defaultdict(list)
        for path in paths:
            digest = md5_of(path)
            if digest:
                by_hash[digest].append(path)
        for digest, same in by_hash.items():
            if len(same) > 1:
                waste = size * (len(same) - 1)
                groups.append((waste, size, same))
    groups.sort(key=lambda g: g[0], reverse=True)
    return groups


def main():
    parser = argparse.ArgumentParser(description="检测重复文件")
    parser.add_argument("roots", nargs="*", default=None,
                        help="扫描目录，默认 ~/Downloads ~/Desktop ~/Documents")
    parser.add_argument("--min-mb", type=float, default=0.5,
                        help="最小文件大小（MB），默认 0.5")
    parser.add_argument("--top", type=int, default=25,
                        help="输出前 N 组，默认 25")
    args = parser.parse_args()

    roots = args.roots or DEFAULT_ROOTS
    min_bytes = int(args.min_mb * 1024 * 1024)

    groups = find_duplicates(roots, min_bytes)
    total = sum(g[0] for g in groups)

    print(f"扫描范围: {', '.join(roots)}")
    print(f"重复组数: {len(groups)}   可回收总量: {total / 1024 / 1024:.1f} MB\n")

    for waste, size, same in groups[: args.top]:
        print(f"[{waste / 1024 / 1024:.1f} MB 可回收 | 单份 {size / 1024 / 1024:.1f} MB | {len(same)} 份]")
        for path in same:
            print("   ", path)
        print()

    print("提醒：删除前确认是否为项目独立资源或有意的版本对照，只有渲染管线中间产物可安全清理。")


if __name__ == "__main__":
    main()
