#!/usr/bin/env python3
"""Step 2 真实 IMA 查重: 拉取目标文件夹全部标题, 与 top3 比对"""
import json
import subprocess
import sys

KB = "ima_kb_cAS2tUN4"
FOLDER = "folder_7489478742522939"


def call(tool, args):
    out = subprocess.run(
        ["python3", "/tmp/ima_mcp_client.py", "call", tool, json.dumps(args, ensure_ascii=False)],
        capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
    except Exception:
        return None
    res = d.get("result", {})
    for c in res.get("content", []):
        if c.get("type") == "text":
            try:
                return json.loads(c["text"])
            except Exception:
                return {"_raw": c["text"]}
    return res


def fetch_titles():
    titles = []
    cursor = ""
    pages = 0
    while True:
        args = {"knowledge_base_id": KB, "folder_id": FOLDER, "limit": 50, "cursor": cursor}
        d = call("get_knowledge_list", args)
        if not d:
            print("❌ get_knowledge_list 失败")
            break
        if "code" in d and d.get("code") not in (0, None):
            print("❌ 错误:", d.get("code"), d.get("msg"))
            break
        data = d.get("data", d)
        items = data.get("knowledge_list", []) or data.get("list", []) or []
        for it in items:
            titles.append({
                "title": it.get("title", ""),
                "media_id": it.get("media_id", ""),
                "create_time": it.get("create_time", ""),
            })
        pages += 1
        cursor = data.get("next_cursor", "")
        if data.get("is_end", True) or not cursor or pages > 20:
            break
    return titles, pages


if __name__ == "__main__":
    titles, pages = fetch_titles()
    print(f"📄 页数: {pages}, 条目数: {len(titles)}")
    json.dump(titles, open("/tmp/ima_existing_titles.json", "w"), ensure_ascii=False, indent=1)
    for t in titles[:5]:
        print("  -", t["title"][:70])
    print("  ...")
    for t in titles[-3:]:
        print("  -", t["title"][:70])
