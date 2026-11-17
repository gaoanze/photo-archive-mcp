# -*- coding: utf-8 -*-
"""可配置项集中管理：图片扩展名、跳过目录、缩略图参数、标签词表等。

默认值与历史行为保持一致；调用方可传入覆盖字典，或从 JSON 配置文件读取。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

#: 参与归档的图片扩展名（小写，含点）
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp"}

#: 系统变换缓存 / 占位目录，无有效图片，递归扫描时直接剔除
SKIP_DIR_MARKS = (".transforms", ".thumbnails", "thumbnails", ".gs", ".trashed",
                  ".trashed-100", "videos", "Video")

#: 缩略图默认参数
DEFAULT_THUMB_MAX_SIDE = 320
DEFAULT_THUMB_QUALITY = 78

#: 感知哈希默认缩略尺寸（越小越粗，速度越快）
PHASH_SIZE = 8

#: 感知哈希汉明距离阈值；不大于该值视为「疑似相似」
PHASH_DISTANCE = 6


def defaults() -> Dict[str, Any]:
    """返回默认配置字典。"""
    return {
        "image_exts": sorted(IMAGE_EXTS),
        "skip_dir_marks": list(SKIP_DIR_MARKS),
        "thumb_max_side": DEFAULT_THUMB_MAX_SIDE,
        "thumb_quality": DEFAULT_THUMB_QUALITY,
        "phash_size": PHASH_SIZE,
        "phash_distance": PHASH_DISTANCE,
        # 常见内容标签词表（仅作网页建议/提示，不强制）
        "tag_suggestions": ["现场实拍", "实验操作记录", "仪器读数", "谱图",
                            "数据表格截图", "检测记录图", "微信传输图", "其他"],
        # HEIC 是否在归档时转成 JPG（True 转；False 保留原片）
        "convert_heic": True,
        # 质量筛查阈值：灰度方差低于 blur_threshold 判模糊；亮度越界判过暗/过亮
        "quality": {
            "blur_threshold": 100.0,
            "brightness_min": 30,
            "brightness_max": 235,
        },
        # 压缩副本默认参数
        "compress": {
            "max_side": 1600,
            "quality": 82,
        },
        # 扫描缓存：未变文件按 mtime+size 复用上一次的指纹/日期/尺寸
        "cache": {
            "enabled": True,
        },
        # 并发：指纹解码与缩略图生成的工作线程数；1 表示串行
        "concurrency": {
            "workers": 4,
        },
    }


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """嵌套合并：字典键递归合并，其余值以 ``extra`` 为准。"""
    for key, val in extra.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def load_config(path: Optional[str], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """合并 默认值 ← 配置文件 ← 调用方覆盖（嵌套字典深合并）。

    :param path: 可选 JSON 配置文件路径。
    :param overrides: 可选覆盖字典，优先级最高。
    """
    cfg = defaults()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        if isinstance(file_cfg, dict):
            cfg = _deep_merge(cfg, file_cfg)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    return cfg
