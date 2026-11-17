# -*- coding: utf-8 -*-
"""标签建议、历史词表记忆与实验分组。

- 标签建议：按文件名/相册关键词规则给出候选标签；人工确认后可写回计划。
- 词表记忆：跨批次读取历史归档清单里用过的标签与当日总结，补充候选词表。
- 实验分组：计划条目可带 ``experiment``，归档时在输出目录下再分一层实验目录。

本模块只做确定性规则匹配，不做图像内容理解。
"""
from __future__ import annotations

import collections
import json
import os
from typing import Any, Dict, List, Optional

from . import utils

#: 关键词 → 标签规则（命中即作为候选；顺序即优先级，先匹配先返回）
KEYWORD_RULES: List[Dict[str, Any]] = [
    {"tag": "数据表格截图", "keys": ["screenshot", "screen", "截图", "table", "excel", "sheet"]},
    {"tag": "谱图", "keys": ["spectrum", "spectra", "nmr", "hplc", "gc", "peak", "谱"]},
    {"tag": "仪器读数", "keys": ["reading", "meter", "display", "读数", "仪器", "scale"]},
    {"tag": "检测记录图", "keys": ["result", "report", "检测", "record", "report"]},
    {"tag": "微信传输图", "keys": ["wechat", "wei xin", "wx", "mmexport", "微信"]},
]

#: 相册名 → 标签规则
ALBUM_RULES: List[Dict[str, Any]] = [
    {"tag": "数据表格截图", "keys": ["screenshot", "截图"]},
    {"tag": "微信传输图", "keys": ["wechat", "wei xin", "微信"]},
]

DEFAULT_TAG = "其他"


def suggest_tag(name: str, album: str = "",
                tag_suggestions: Optional[List[str]] = None) -> str:
    """根据文件名与相册名给出建议标签；规则未命中返回 ``其他``。

    返回值一定在 ``tag_suggestions`` 词表内（若提供），便于网页下拉对齐。
    """
    text = f"{name} {album}".lower()
    for rule in KEYWORD_RULES:
        if any(k in text for k in rule["keys"]):
            return _align(rule["tag"], tag_suggestions)
    for rule in ALBUM_RULES:
        if any(k in album.lower() for k in rule["keys"]):
            return _align(rule["tag"], tag_suggestions)
    return _align(DEFAULT_TAG, tag_suggestions)


def _align(tag: str, suggestions: Optional[List[str]]) -> str:
    if not suggestions:
        return tag
    if tag in suggestions:
        return tag
    # 词表中找语义相近项；找不到则保留原标签
    for s in suggestions:
        if s in tag or tag in s:
            return s
    return suggestions[0] if suggestions else tag


def suggest_tags_for_records(records: List[Dict[str, Any]],
                             tag_suggestions: Optional[List[str]] = None
                             ) -> Dict[str, str]:
    """批量给记录生成 ``{文件名: 建议标签}`` 映射。"""
    out: Dict[str, str] = {}
    for r in records:
        out[str(r["name"])] = suggest_tag(
            str(r.get("name", "")), str(r.get("album", "")), tag_suggestions)
    return out


def load_history_vocab(out_dir: str) -> Dict[str, List[str]]:
    """从已有归档清单读取历史用过的标签与当日总结，用于跨批次沿用。

    返回 ``{"tags": [...], "summaries": [...]}``，去重并按使用频次排序。
    """
    manifest_path = os.path.join(out_dir, "归档清单.json")
    tags: "collections.Counter[str]" = collections.Counter()
    summaries: "collections.Counter[str]" = collections.Counter()
    if os.path.exists(manifest_path):
        try:
            rows = utils.read_json(manifest_path)
        except Exception:
            rows = []
        for m in rows:
            if m.get("tag"):
                tags[str(m["tag"])] += 1
            folder = str(m.get("folder", ""))
            # 文件夹名形如 日期-总结，去掉日期前缀即当日总结
            parts = folder.split("-", 3)
            if len(parts) >= 4:
                summaries[parts[3]] += 1
    return {
        "tags": [t for t, _ in tags.most_common()],
        "summaries": [s for s, _ in summaries.most_common()],
    }


def merge_vocab(base: List[str], history: List[str]) -> List[str]:
    """合并默认词表与历史词表，去重保序，历史项靠前。"""
    seen: set[str] = set()
    merged: List[str] = []
    for item in list(history) + list(base):
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def group_experiments(plan: List[Dict[str, Any]]) -> "collections.OrderedDict[str, List[Dict[str, Any]]]":
    """按 ``experiment`` 字段分组；缺省归入 ``未分组实验``。"""
    grouped: "collections.OrderedDict[str, List[Dict[str, Any]]]" = collections.OrderedDict()
    for item in plan:
        exp = str(item.get("experiment") or "未分组实验")
        grouped.setdefault(exp, []).append(item)
    return grouped
