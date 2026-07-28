#!/usr/bin/env python3
"""
Step 1: 拉 30 页 → 过去 24h 窗口 → 名称去重 → Top 3
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

JQS = "/Users/ytf/Library/Python/3.9/bin/jqcli"  # 可改
TOP_N = 3
NAME_SIM_THRESHOLD = 0.80
WINDOW_HOURS = 24
MAX_PAGES = 30
CACHE_FILE = Path("/tmp/jq_candidates_cache.json")
TOP3_FILE = Path("/tmp/jq_top3.json")


def fetch_candidates() -> list:
    """从 jqcli 拉取最近 MAX_PAGES 页"""
    r = subprocess.run(
        [JQS, "--format", "json", "community", "latest",
         "--page-size", "50", "--max-pages", str(MAX_PAGES)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"jqcli 失败: {r.stderr}")
    return json.loads(r.stdout).get("items", [])


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def deduplicate_by_name(items: list) -> tuple:
    """去重：保留 view_count 更高的"""
    items_sorted = sorted(items, key=lambda x: x.get("view_count", 0), reverse=True)
    kept, removed = [], []
    for item in items_sorted:
        is_dup = False
        for k in kept:
            if name_similarity(item.get("title", ""), k.get("title", "")) >= NAME_SIM_THRESHOLD:
                is_dup = True
                removed.append(item.get("title"))
                break
        if not is_dup:
            kept.append(item)
    return kept, removed


def main():
    # 1. 拉候选
    print(f"📦 拉取 {MAX_PAGES} 页...")
    items = fetch_candidates()
    print(f"   总计 {len(items)} 条")
    
    # 2. 24h 窗口
    now = datetime.now()
    cutoff = now - timedelta(hours=WINDOW_HOURS)
    recent = []
    for it in items:
        try:
            ts = datetime.strptime(it["published_at"], "%Y-%m-%d %H:%M:%S")
            if ts >= cutoff:
                recent.append(it)
        except: pass
    
    print(f"⏰ {cutoff} ~ {now}")
    print(f"📅 过去 {WINDOW_HOURS}h: {len(recent)} 条")
    
    # 3. 过滤有 backtest
    bt_items = [i for i in recent if i.get("backtest", {}).get("id")]
    print(f"🔬 带 backtest: {len(bt_items)} 条")
    
    # 4. 名称去重
    unique, removed = deduplicate_by_name(bt_items)
    print(f"✨ 去重后: {len(unique)} 条 (去掉 {len(removed)} 条)")
    
    # 5. 取 Top N
    top_n = sorted(unique, key=lambda x: x.get("view_count", 0), reverse=True)[:TOP_N]
    
    print(f"\n🏆 Top {TOP_N}:")
    for i, it in enumerate(top_n, 1):
        print(f"  {i}. [{it['view_count']} views] {it['title'][:50]}")
        print(f"     POST_ID: {it['id']}  发表于: {it['published_at']}")
    
    # 6. 保存
    TOP3_FILE.write_text(json.dumps({
        "window_start": cutoff.strftime('%Y-%m-%d %H:%M:%S'),
        "window_end": now.strftime('%Y-%m-%d %H:%M:%S'),
        "top3": top_n,
    }, ensure_ascii=False, indent=2))
    print(f"\n💾 {TOP3_FILE}")


if __name__ == "__main__":
    main()
