# -*- coding: utf-8 -*-
"""总行部门职能职责梳理 —— 留痕写入与单部门 Sheet 骨架。

确定性工具：把"带增删改留痕的职责条目"写进 xlsx。内容由 agent 在对话中构造，
本脚本只负责"怎么写对"（颜色、横线、8 位 ARGB、行高）。

用法（在生成脚本里 import 或直接复制函数）：
    from duty_trace import COLORS, f_runs, build_dept_sheet
"""
import openpyxl
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# 颜色约定（固定，8 位 ARGB）
COLORS = {
    'same':     'FF000000',  # 未改动（黑）
    'add':      'FF006400',  # 新增（深绿，不加线）
    'del':      'FF006400',  # 删除（深绿 + 横线）
    'mod':      'FF0000FF',  # 修改（深蓝）
    'conflict': 'FFFF00FF',  # 冲突（品红）
    'cross':    'FFFF6600',  # 交叉重叠（橙）
}

_HEADER_FILL = PatternFill('solid', fgColor='FFD9E2F3')
_HEADER_FONT = Font(name='微软雅黑', size=10, bold=True, color='FF1F3864')
_BODY_FONT = Font(name='微软雅黑', size=10, color='FF000000')
_WRAP = Alignment(wrap_text=True, vertical='top')
_WRAP_C = Alignment(wrap_text=True, vertical='center', horizontal='center')
_thin = Side(style='thin', color='FFBFBFBF')
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def f_runs(runs):
    """runs: list[(text, kind)]，kind ∈ same/add/del/mod/conflict/cross。
    返回 CellRichText，del 自动加横线。"""
    parts = []
    for text, kind in runs:
        if text == '':
            continue
        color = COLORS[kind]
        strike = (kind == 'del')
        parts.append(TextBlock(
            InlineFont(rFont='微软雅黑', sz=10, color=color, strike=strike), text))
    return CellRichText(*parts)


def f_plain(text, color='FF000000', strike=False, bold=False, sz=10):
    return CellRichText(TextBlock(
        InlineFont(rFont='微软雅黑', sz=sz, color=color, strike=strike, b=bold), text))


def _style(c, font=None, fill=None, align=None):
    c.font = font or _BODY_FONT
    if fill:
        c.fill = fill
    c.alignment = align or _WRAP
    c.border = _BORDER


def build_dept_sheet(wb, name, main_func, items, note='', cross=''):
    """在 wb 里新建一个部门 Sheet。

    name      : 部门名称（Sheet 名）
    main_func : 主要职能（一段话，纯文本）
    items     : list[(runs, d_note)]，runs 是 f_runs 入参格式，d_note 是 D 列备注（可空）
    note      : 部门级说明（冲突/调整依据，用品红标【说明】）
    cross     : 交叉重叠提示（用橙色标【交叉重叠】）
    """
    ws = wb.create_sheet(name)
    ws.column_dimensions['A'].width = 16
    ws.column_dimensions['B'].width = 56
    ws.column_dimensions['C'].width = 90
    ws.column_dimensions['D'].width = 30
    for col, h in zip('ABCDE', ['部门名称', '主要职能', '具体职责', '备注', '调整后职责']):
        c = ws[f'{col}1']
        c.value = h
        _style(c, _HEADER_FONT, _HEADER_FILL, _WRAP_C)
    _style(ws.cell(row=2, column=1, value=name))
    _style(ws.cell(row=2, column=2, value=f_plain(main_func)))
    row = 2
    for runs, d_note in items:
        _style(ws.cell(row=row, column=3, value=f_runs(runs)))
        if d_note:
            dn = ws.cell(row=row, column=4, value=d_note)
            _style(dn)
            dn.font = Font(name='微软雅黑', size=9, color='FF7F7F7F')
        row += 1
    if note:
        nr = row + 1
        cn = ws.cell(row=nr, column=3, value=f_plain('【说明】' + note, color=COLORS['conflict']))
        _style(cn)
        cn.fill = PatternFill('solid', fgColor='FFFCE4EC')
        ws.merge_cells(start_row=nr, start_column=2, end_row=nr, end_column=5)
    if cross:
        cr = (row + 1 if not note else row + 3)
        cc = ws.cell(row=cr, column=3, value=f_plain('【交叉重叠】' + cross, color=COLORS['cross']))
        _style(cc)
        cc.fill = PatternFill('solid', fgColor='FFFFF4E5')
        ws.merge_cells(start_row=cr, start_column=2, end_row=cr, end_column=5)
    return ws


def build_overview(wb, rows):
    """rows: list[(序号, 调整前部门, 是否调整, 职能是否需调, 后续是否变, 后续变动)]。"""
    ws = wb.create_sheet('总览')
    for i, h in enumerate(['序号', '部门名称', '部门是否发生调整',
                           '已有职能是否需要调整', '后续职能是否发生变化', '后续变动情况'], 1):
        c = ws.cell(row=1, column=i, value=h)
        _style(c, _HEADER_FONT, _HEADER_FILL, _WRAP_C)
    for r, row in enumerate(rows, 2):
        for i, v in enumerate(row, 1):
            _style(ws.cell(row=r, column=i, value=v))
    widths = [6, 40, 14, 14, 14, 60]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws
