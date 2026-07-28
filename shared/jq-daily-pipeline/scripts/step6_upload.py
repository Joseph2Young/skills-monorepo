#!/usr/bin/env python3
"""
Step 6: 上传到 IMA 当年文件夹
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ima_api

DEDUP_FILE = Path("/tmp/jq_dedup_result.json")
UPLOAD_DIR = Path("/tmp/jq_uploads")


def detect_md_media_type(file_path: Path) -> tuple:
    """markdown 文件预检"""
    size = file_path.stat().st_size
    return size, "text/markdown", "md", 7  # media_type 7 = markdown


def upload_one(file_path: Path) -> dict:
    print(f"\n📤 {file_path.name}")
    file_name = file_path.name
    file_size, content_type, file_ext, media_type = detect_md_media_type(file_path)
    
    target_folder = json.load(open(DEDUP_FILE))["target_folder_id"]
    
    # 查重
    if ima_api.check_repeated(file_name, media_type, target_folder):
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        new_name = f"{Path(file_name).stem}_{ts}{Path(file_name).suffix}"
        new_path = file_path.parent / new_name
        file_path = new_path.rename(new_path)
        file_name = new_name
    
    # 创建媒体
    try:
        media = ima_api.create_media(file_name, file_size, content_type, file_ext)
    except Exception as e:
        return {"ok": False, "stage": "create_media", "error": str(e)}
    
    media_id = media.get("media_id")
    cos_cred = media.get("cos_credential", {})
    cos_key = media.get("cos_key", "")
    print(f"   media_id: {media_id[:20]}...")
    
    # COS 上传
    try:
        ima_api.upload_to_cos(file_path, cos_cred, content_type, timeout=300)
    except Exception as e:
        return {"ok": False, "stage": "cos_upload", "error": str(e)}
    print(f"   ✅ COS 上传完成")
    
    # 关联到知识库
    try:
        ima_api.add_knowledge(media_id, file_name, target_folder, media_type,
                              cos_key, file_size, file_name)
    except Exception as e:
        return {"ok": False, "stage": "add_knowledge", "error": str(e)}
    print(f"   ✅ 已添加到 IMA")
    
    return {"ok": True, "file_name": file_name}


def main():
    if not DEDUP_FILE.exists():
        print(f"❌ 找不到 {DEDUP_FILE}")
        sys.exit(1)
    
    md_files = sorted(UPLOAD_DIR.glob("*.md"))
    if not md_files:
        print("⚠️ 没有待上传文件")
        return
    
    results = []
    for f in md_files:
        r = upload_one(f)
        results.append({"file": f.name, **r})
    
    print(f"\n{'='*60}")
    print(f"📊 上传汇总")
    print(f"{'='*60}")
    for r in results:
        status = "✅" if r.get("ok") else "❌"
        print(f"  {status} {r['file']}  stage={r.get('stage', 'ok')}")
    
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n成功: {ok}/{len(results)}")


if __name__ == "__main__":
    main()
