# -*- coding: utf-8 -*-
"""通用辅助：文件名净化、日期解析、JSON 读写与目录规划。"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from typing import Any, Dict, List, Optional

# Windows / Git 都不允许出现在文件名里的字符
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')


def safe_name(text: str) -> str:
    """去掉文件名中的非法字符，压缩空白与多余连字符。"""
    text = _INVALID_CHARS.sub("", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[-_]{2,}", "-", text)
    return text.strip("-_ ")


def parse_date(name: str) -> str:
    """从文件名解析日期，返回 YYYY-MM-DD；解析不到返回 ``未知日期``。

    支持华为/安卓常见命名：``20260915_xxxx.jpg``、``image_1726350000.jpg``、
    ``image_1726350000000.jpg``。
    """
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", name)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}"
    m = re.search(r"image_(\d{13})", name)
    if m:
        return _dt.datetime.fromtimestamp(int(m.group(1)) / 1000).strftime("%Y-%m-%d")
    m = re.search(r"image_(\d{10})", name)
    if m:
        return _dt.datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d")
    return "未知日期"


def album_of(rel: str) -> str:
    """从相对路径提取相册名。"""
    parts = [p for p in rel.split("/") if p]
    for key in ("Pictures", "DCIM", "Camera", "微信", "WeiXin"):
        if key in parts:
            i = parts.index(key)
            return parts[i + 1] if i + 1 < len(parts) else key
    if len(parts) >= 3:
        return parts[2]
    return "其他"


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def count_images(folder: str) -> int:
    exts = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp"}
    n = 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if os.path.splitext(f)[1].lower() in exts:
                n += 1
    return n


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}TB"
