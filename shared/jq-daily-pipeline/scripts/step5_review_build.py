#!/usr/bin/env python3
"""
Step 5: AI 审查 (聚宽策略审查分类提示词 v1.0) + 生成 markdown

入库命名格式 (主人规则 2026-07-29):
  {year}_{Tcode}_{Tname}_{author_safe}_{title_core}_s{sharpe}.md
  例: 2026_T07_板块轮动_Tcya_减法出奇迹_一个ETF轮动策略的科学提纯之路_s0.85.md

- author_safe: 去空白 + 去特殊字符 (<>:"/\\|?*), 截 30 字符
- sharpe: 末段 `_s{sharpe:.2f}`, 如 _s0.85 / _s2.40
- title_core: 标点换 _, 去空白, 截 50 字符
- agent 可在 dedup_result.candidates[i] 里填 `condensed_title_core` 字段覆盖
- 总长度超过 MAX_FILENAME_LEN 时告警, 提示 agent 自己浓缩
"""
import json
import re
from datetime import datetime
from pathlib import Path

DEDUP_FILE = Path("/tmp/jq_dedup_result.json")
SHARPE_FILE = Path("/tmp/jq_real_sharpe.json")
REVIEWS_FILE = Path("/tmp/jq_reviews.json")
UPLOAD_DIR = Path("/tmp/jq_uploads")
CODES_DIR = Path("/tmp/jq_codes")
# Sharpe 过滤条件: 0.8 < sharpe <= 3 (主人规则 2026-07-28)
SHARPE_MIN = 0.8
SHARPE_MAX = 3.0
# 入库文件名总长度上限 (含 .md 后缀), 超过 agent 应该自己 condensed_title_core
MAX_FILENAME_LEN = 80

TYPES = {
    "T01": "趋势跟踪", "T02": "均值回归", "T03": "多因子选股",
    "T04": "指数增强", "T05": "事件驱动", "T06": "资金流向",
    "T07": "板块轮动", "T08": "统计套利", "T09": "技术形态",
    "T10": "ML/AI选股", "T11": "波动率策略", "T12": "成长股策略",
}

# 决策树: (类型, (关键词列表, AND/OR), 理由)
DECISION_RULES = [
    ("T04", (["set_benchmark", "get_index_stocks"], "AND"), "对标指数+成分内选股"),
    ("T08", (["协整", "价差", "Z-score", "对冲", "pairs"], "OR"), "配对/多空对冲"),
    ("T02", (["RSI", "KDJ", "布林", "BIAS", "乖离", "reversal", "反转", "超卖"], "OR"), "反转"),
    ("T10", (["XGBoost", "LSTM", "tensorflow", "torch", "RandomForest"], "OR"), "ML训练预测"),
    ("T03", (["get_fundamentals", "get_factor_values", "Alpha101", "Alpha191"], "OR"), "多因子"),
    ("T06", (["北向", "融资余额", "龙虎榜", "大单", "资金流"], "OR"), "资金流向"),
    ("T05", (["业绩预告", "回购", "分红", "事件", "公告"], "OR"), "事件驱动"),
    ("T07", (["get_industry_stocks", "get_concept_stocks", "ETF池", "etf_pool"], "OR"), "板块轮动"),
    ("T09", (["CDL", "W底", "旗形", "吞没", "锤子", "jqmt"], "OR"), "技术形态"),
    ("T11", (["ATR", "vol-targeting", "波动率"], "OR"), "波动率"),
    ("T12", (["PEG", "高增速", "inc_revenue"], "OR"), "成长股"),
    ("T01", (["momentum", "MA", "EMA", "均线", "金叉", "多头排列", "ADX", "唐奇安", "动量"], "OR"), "趋势"),
]


def classify(code: str, init_code: str) -> tuple:
    full = code + "\n" + init_code
    for type_code, (keywords, mode), reason in DECISION_RULES:
        if mode == "AND":
            if all(kw in full for kw in keywords):
                return type_code, TYPES[type_code], reason
        else:
            if any(kw in full for kw in keywords):
                return type_code, TYPES[type_code], reason
    return "T11", TYPES["T11"], "默认波动率"


def extract_title_core(title: str) -> str:
    """从原标题提取核心: 标点换 _ → 去空白 → 多下划线合并 → 截 50 字符

    agent 可在 candidate 里填 condensed_title_core 覆盖这个结果
    """
    t = re.sub(r'[?!？！,，:：;；。、]+', '_', title)
    t = re.sub(r'\s+', '', t)
    t = re.sub(r'_+', '_', t).strip('_')
    return t[:50]


def safe_author(author: str) -> str:
    """作者字段去空白 + 去文件系统非法字符, 截 30 字符"""
    a = re.sub(r'\s+', '', author or '')
    a = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '', a)
    return a[:30]


def sharpe_segment(sharpe) -> str:
    """Sharpe 段: s0.85 / s2.40, None 退化为 s?
    注意不带前导下划线 (build_filename 用 _ join, 否则会双下划线)
    """
    if sharpe is None:
        return "s?"
    try:
        return f"s{float(sharpe):.2f}"
    except (TypeError, ValueError):
        return "s?"


def build_filename(year: str, tcode: str, tname: str, author: str,
                   sharpe, title_core: str) -> tuple[str, int]:
    """构造最终文件名 + 返回含 .md 后缀的总长度

    新格式: {year}_{Tcode}_{Tname}_{author_safe}_{title_core}_s{sharpe}.md
    Sharpe 段放最后, 方便人眼按质量排序时一眼看到尾部
    """
    parts = [
        year,
        tcode,
        tname,
        safe_author(author),
        title_core,
        sharpe_segment(sharpe),
    ]
    name = "_".join(parts)
    return name, len(name) + len(".md")


def build_review(c: dict, code: str, sharpe=None) -> dict:
    init = re.search(r'def initialize\(context\):(.*?)(?=\ndef |\Z)', code, re.DOTALL)
    init_code = init.group(1) if init else ""
    primary, primary_name, reason = classify(code, init_code)

    year = c["published_at"][:4]

    # 兼容 author dict 和 author_name 平铺字段
    author = c.get("author")
    if isinstance(author, dict):
        author_name = author.get("name", "")
    else:
        author_name = c.get("author_name") or (str(author) if author else "")

    # 浓缩标题: agent 可在 dedup_result.candidates[i] 里填 condensed_title_core 覆盖
    title_core = c.get("condensed_title_core") or extract_title_core(c["title"])

    new_name, full_len = build_filename(
        year=year,
        tcode=primary,
        tname=primary_name,
        author=author_name,
        sharpe=sharpe,
        title_core=title_core,
    )

    return {
        "meta": {
            "post_id": c["id"],
            "original_title": c["title"],
            "author": author_name,
            "published_at": c["published_at"],
            "view_count": c["view_count"],
            "year": year,
            "sharpe": sharpe,
            "ai_new_name": new_name,
            "filename_len": full_len,
            "too_long": full_len > MAX_FILENAME_LEN,
        },
        "strategy_classification": {
            "primary_type": primary,
            "primary_name": primary_name,
            "confidence": "中",
            "classification_reason": reason,
        },
        "risk_assessment": {
            "overall_risk_level": "严重" if "jqmt" in code else "中",
        },
    }


def main():
    if not DEDUP_FILE.exists() or not SHARPE_FILE.exists():
        print("❌ 缺少 step2/step4 输出文件")
        return

    data = json.load(open(DEDUP_FILE))
    candidates = data.get("top3_after_dedup", [])
    sharpes = {x["sid"]: x for x in json.load(open(SHARPE_FILE))}

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # 清空旧
    for f in UPLOAD_DIR.glob("*.md"):
        f.unlink()

    reviews = {}
    for i, c in enumerate(candidates, 1):
        sid = f"s{i}"
        code_path = CODES_DIR / f"{sid}_code.json"
        if not code_path.exists():
            continue

        try:
            code = json.load(open(code_path)).get("code", "")
        except:
            continue

        # Sharpe 过滤: 0.8 < sharpe <= 3
        real = sharpes.get(sid, {})
        sharpe = real.get("sharpe")
        if sharpe is None:
            print(f"  ❌ {sid} Sharpe=None 跳过 (无 Sharpe)")
            continue
        if sharpe <= SHARPE_MIN:
            print(f"  ❌ {sid} Sharpe={sharpe:.4f} 跳过 (<={SHARPE_MIN})")
            continue
        if sharpe > SHARPE_MAX:
            print(f"  ❌ {sid} Sharpe={sharpe:.4f} 跳过 (>{SHARPE_MAX}, 过度拟合)")
            continue

        review = build_review(c, code, sharpe=sharpe)
        review["real_backtest"] = real
        reviews[sid] = review

        # 长度超阈值告警 — 提醒 agent 应该在 dedup_result 里填 condensed_title_core
        if review["meta"]["too_long"]:
            print(f"  ⚠️  {sid} 文件名 {review['meta']['filename_len']} 字符 > {MAX_FILENAME_LEN}, "
                  f"agent 应在 candidate 里填 condensed_title_core 浓缩标题")
            print(f"      当前: {review['meta']['ai_new_name']}.md")

        new_name = review["meta"]["ai_new_name"]
        md = f"""# {new_name}

**原帖**: https://www.joinquant.com/view/community/detail/{review['meta']['post_id']}  
**作者**: {review['meta']['author']}  
**热度**: {review['meta']['view_count']} views  
**分类**: {review['strategy_classification']['primary_type']} {review['strategy_classification']['primary_name']}  
**Sharpe**: {sharpe:.4f}  
**回测区间**: 2019-01-01 ~ T-1

## 策略代码

```python
{code}
```

## 完整审查

```json
{json.dumps(review, ensure_ascii=False, indent=2)}
```

---
*由 jq-daily-pipeline 自动生成 · 提示词: 聚宽策略审查分类提示词 v1.0*
"""
        (UPLOAD_DIR / f"{new_name}.md").write_text(md, encoding="utf-8")
        print(f"  ✅ {new_name}.md")

    REVIEWS_FILE.write_text(json.dumps(reviews, ensure_ascii=False, indent=2))
    print(f"\n💾 {REVIEWS_FILE}")


if __name__ == "__main__":
    main()
