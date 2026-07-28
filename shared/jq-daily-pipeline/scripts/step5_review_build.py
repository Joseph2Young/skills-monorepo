#!/usr/bin/env python3
"""
Step 5: AI 审查 (聚宽策略审查分类提示词 v1.0) + 生成 markdown
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
# Sharpe 过滤条件: 1 < sharpe < 3 (主人规则 2026-07-28)
SHARPE_MIN = 1.0
SHARPE_MAX = 3.0

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
    t = re.sub(r'[?!？！,，:：;；。、]+', '_', title)
    t = re.sub(r'_+', '_', t).strip('_')
    return t[:50]


def build_review(c: dict, code: str) -> dict:
    init = re.search(r'def initialize\(context\):(.*?)(?=\ndef |\Z)', code, re.DOTALL)
    init_code = init.group(1) if init else ""
    primary, primary_name, reason = classify(code, init_code)
    
    year = c["published_at"][:4]
    title_core = extract_title_core(c["title"])
    new_name = f"{year}_{primary}_{primary_name}_{title_core}"
    
    return {
        "meta": {
            "post_id": c["id"],
            "original_title": c["title"],
            "author": c["author"]["name"],
            "published_at": c["published_at"],
            "view_count": c["view_count"],
            "year": year,
            "ai_new_name": new_name,
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
        
        review = build_review(c, code)
        review["real_backtest"] = sharpes.get(sid, {})
        reviews[sid] = review
        
        # 生成 markdown (Sharpe 过滤: 1 < sharpe < 3)
        real = sharpes.get(sid, {})
        sharpe = real.get("sharpe")
        if sharpe is None:
            print(f"  ❌ {sid} Sharpe=None 跳过 (无 Sharpe)")
            continue
        if sharpe <= SHARPE_MIN:
            print(f"  ❌ {sid} Sharpe={sharpe:.4f} 跳过 (<={SHARPE_MIN})")
            continue
        if sharpe >= SHARPE_MAX:
            print(f"  ❌ {sid} Sharpe={sharpe:.4f} 跳过 (>={SHARPE_MAX}, 过度拟合)")
            continue
        
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
