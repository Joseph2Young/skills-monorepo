# 留痕技术（openpyxl 富文本 + 语块级 diff + 条目对齐）

## 一、读取：必须 rich_text=True

读取带分段着色的 xlsx，必须：

```python
wb = openpyxl.load_workbook(path, rich_text=True)
```

否则单元格内 run 级颜色会被抹平（原稿的分段着色会丢）。

## 二、写入：CellRichText + 8 位 ARGB

```python
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

def run(text, color='FF000000', strike=False, sz=10):
    return TextBlock(InlineFont(rFont='微软雅黑', sz=sz, color=color, strike=strike), text)
```

三条硬约束：
1. **颜色必须给 8 位 ARGB**（如 `FF006400`）。写 6 位 `006400` 会被 openpyxl 补成 `00006400`（全透明）。
2. **color 必须显式给**，不要 `None`——`None` 时 openpyxl 不写 `<color>`，该 run 会继承单元格底色（原稿红字会把新文本染红）。
3. 编辑工具（editor_sdk 的 sheet 写入）只支持整格同色，**单元格内分段着色必须走 openpyxl**。

## 三、修改标记：语块级 diff，不用字符级

字符级 diff 会把中文词拆成绿斑。正确做法：按标点切分 token 后再 `difflib.SequenceMatcher`。

```python
import re, difflib
def tokenize(s):
    return re.findall(r'[^，。；、；：\n]+[，。；、；：]?', s)
```

## 四、条目对齐：全局最优匹配

新旧条目数不同时，逐行 diff 会整体错位。必须先做全局最优匹配：

```python
# 对每个新条目，找旧条目中 ratio 最高且 >= 0.42 的作留痕基准
matcher = difflib.SequenceMatcher(None, old_text, new_text)
if matcher.ratio() >= 0.42:
    # 用 old_text 作留痕基准，标删除线；new_text 标改写色
else:
    # 未匹配的旧条目整条划删，新条目整条标新增
```

匹配上的用其原文作留痕基准（`revise_pair`）；未匹配的整条划删。条目大规模整合重写时（如计财部），可能仅少数能匹配，其余按「被合并/替换」整条划删——这是如实反映，不是错误。

## 五、行高：按各列行数取最大重算

追加内容后，行高按各列文本行数增量调高（不是固定值）。列宽决定每行字数（如列宽 76 ≈ 34 字/行），据此估算行数。

## 六、文本未变的单元格一律不碰

文本完全未变的单元格直接 return，一格不动，保留原稿既有痕迹。

## 七、整表重建（改行结构时唯一安全做法）

本文件单元格为 inline-string，openpyxl 的 `insert_rows`／`delete_rows` 在保存时会**随机丢失被移动的单元格**（实测：仅 insert + save 即可复现）。需要增行／删行／重排时，一律整表重建：

```python
import openpyxl
from copy import copy

wb = openpyxl.load_workbook(path, rich_text=True)
old = wb[sheet_name]
idx = wb.sheetnames.index(sheet_name)
tabcolor = old.sheet_properties.tabColor
colwidths = {c: old.column_dimensions[c].width for c in 'ABCDE' if c in old.column_dimensions}
hdr = {c: (copy(old.cell(1, c).font), copy(old.cell(1, c).fill),
           copy(old.cell(1, c).alignment), copy(old.cell(1, c).border)) for c in range(1, 6)}

wb.remove(old)
ws = wb.create_sheet(sheet_name)
if wb.sheetnames.index(sheet_name) != idx:
    wb.move_sheet(sheet_name, offset=idx - wb.sheetnames.index(sheet_name))
ws.sheet_properties.tabColor = tabcolor
for c, w in colwidths.items():
    ws.column_dimensions[c].width = w
# 写表头：复用 hdr 快照的 font/fill/alignment/border
# 逐行写数据：value + Font/Alignment/Border + CellRichText（红/灰/黑 runs）
# 重算行高
wb.save(path)
```

要点：
- 快照 tabColor（如黄色待核对标记）、列宽、表头样式，重建后逐项恢复；
- 重建后核验：sheet 总数不变、tab 颜色保留、其余 sheet 未受影响、富文本颜色正确。
