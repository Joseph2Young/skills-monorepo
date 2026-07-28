#!/usr/bin/env python3
"""
Step 2: IMA 年度查重
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ima_api

TOP3_FILE = Path("/tmp/jq_top3.json")
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")


def main():
    if not TOP3_FILE.exists():
        print(f"❌ 找不到 {TOP3_FILE}, 请先跑 step1")
        sys.exit(1)
    
    data = json.load(open(TOP3_FILE))
    candidates = data.get("top3", [])
    if not candidates:
        print("⚠️ 没有候选")
        return
    
    win_start = data.get("window_start", "")
    target_year = win_start[:4] if win_start else str(datetime.now().year)
    print(f"📅 目标年度: {target_year}")
    
    # 查或创建年度文件夹
    try:
        folder_id = ima_api.find_or_create_year_folder(target_year)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)
    print(f"📁 年度文件夹 ID: {folder_id}")
    
    # 取已有标题
    existing = ima_api.get_existing_titles_in_folder(folder_id)
    print(f"📋 文件夹内已有: {len(existing)} 条")
    
    # 过滤
    kept, skipped = [], []
    ai_prefix = f"{target_year}_"
    for c in candidates:
        title = c.get("title", "").strip()
        if title in existing:
            skipped.append((c, "原标题已存在"))
        elif any(t.startswith(ai_prefix) and title[:20] in t for t in existing):
            skipped.append((c, f"AI 命名 '{title[:20]}...' 已入库"))
        else:
            kept.append(c)
    
    print(f"\n✅ 保留: {len(kept)}, ❌ 跳过: {len(skipped)}")
    for c, r in skipped:
        print(f"   ✗ {c.get('title','')[:50]} -- {r}")
    
    data["target_year"] = target_year
    data["target_folder_id"] = folder_id
    data["top3_after_dedup"] = kept
    data["skipped_due_to_dedup"] = [{"title": c.get("title"), "reason": r} for c, r in skipped]
    
    DEDUP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n💾 {DEDUP_FILE}")


if __name__ == "__main__":
    main()
