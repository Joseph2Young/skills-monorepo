#!/usr/bin/env python3
"""
Step 3: 克隆 Top 3 + 拉策略代码
"""
import json
import subprocess
import sys
from pathlib import Path

JQS = "/Users/ytf/Library/Python/3.9/bin/jqcli"
DEDUP_FILE = Path("/tmp/jq_dedup_result.json")
CODES_DIR = Path("/tmp/jq_codes")


def clone_and_fetch(post_id: str, idx: int) -> str:
    """克隆策略并拉代码"""
    print(f"  克隆 {post_id}...")
    r = subprocess.run(
        [JQS, "--format", "json", "community", "clone-strategy", post_id, "--yes"],
        capture_output=True, text=True
    )
    if r.returncode != 0 or not r.stdout.strip():
        print(f"    ❌ 克隆失败: {r.stderr}")
        return ""
    try:
        resp = json.loads(r.stdout)
    except:
        print(f"    ❌ 解析失败: {r.stdout[:200]}")
        return ""
    
    strategy_id = resp.get("strategy_id", "")
    if not strategy_id:
        print(f"    ❌ 没拿到 strategy_id: {resp}")
        return ""
    print(f"    strategy_id: {strategy_id}")
    
    # 拉代码
    code_path = CODES_DIR / f"s{idx}_code.json"
    r = subprocess.run(
        [JQS, "--format", "json", "strategy", "show", strategy_id, "--code"],
        capture_output=True, text=True
    )
    if r.returncode == 0 and r.stdout.strip():
        code_path.write_text(r.stdout)
        code_data = json.loads(r.stdout)
        code_len = len(code_data.get("code", ""))
        print(f"    ✅ 代码已存 ({code_len} chars)")
        return strategy_id
    else:
        print(f"    ❌ 拉代码失败: {r.stderr}")
        return ""


def main():
    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)
    
    data = json.load(open(DEDUP_FILE))
    candidates = data.get("top3_after_dedup", [])
    
    CODES_DIR.mkdir(parents=True, exist_ok=True)
    # 清空旧
    for f in CODES_DIR.glob("*.json"):
        f.unlink()
    
    strategy_ids = []
    for i, c in enumerate(candidates, 1):
        sid = clone_and_fetch(c["id"], i)
        if sid:
            strategy_ids.append(sid)
        else:
            strategy_ids.append("")  # 占位
    
    # 保存
    data["strategy_ids"] = strategy_ids
    DEDUP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    success = sum(1 for s in strategy_ids if s)
    print(f"\n💾 成功克隆 {success}/{len(candidates)} 个")
    if success == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
