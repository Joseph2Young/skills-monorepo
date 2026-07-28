#!/usr/bin/env python3
"""
Step 6 (monitor 模式): 扫描 /tmp/jq_uploads/ 下的 markdown, 写上传 trigger
agent 端 automation 检测 trigger 后用 MCP 工具逐个上传
"""
import json
import os
from pathlib import Path
from datetime import datetime

UPLOAD_DIR = Path("/tmp/jq_uploads")
TRIGGER_FILE = Path("/tmp/jq_upload_trigger.json")


def main():
    if not UPLOAD_DIR.exists():
        return

    md_files = sorted(UPLOAD_DIR.glob("*.md"))
    if not md_files:
        print("⚠️ 没有待上传 markdown")
        TRIGGER_FILE.write_text(json.dumps({"to_upload": []}, ensure_ascii=False, indent=2))
        return

    to_upload = []
    for f in md_files:
        stat = f.stat()
        to_upload.append({
            "file_path": str(f),
            "file_name": f.name,
            "file_size": stat.st_size,
            "content_type": "text/markdown",
            "file_ext": "md",
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

    TRIGGER_FILE.write_text(json.dumps({"to_upload": to_upload}, ensure_ascii=False, indent=2))
    print(f"💾 {TRIGGER_FILE}: {len(to_upload)} 个待上传")


if __name__ == "__main__":
    main()