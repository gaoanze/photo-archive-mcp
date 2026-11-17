# -*- coding: utf-8 -*-
"""图片指纹、重复检测与 EXIF 日期读取。

- 精确重复：按文件字节 SHA-1 判定。
- 疑似相似：按感知哈希（pHash）汉明距离判定，容忍缩放/轻微压缩。
- 日期兜底：文件名解析不到时回退 EXIF 拍摄时间。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def sha1_file(path: str, chunk: int = 1 << 16) -> str:
    """计算文件字节 SHA-1（用于精确去重）。"""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def phash(image: Image.Image, size: int = 8) -> int:
    """计算感知哈希整数；灰度缩略图 → 与均值比较生成位串。"""
    gray = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for i, p in enumerate(pixels):
        if p >= avg:
            bits |= 1 << i
    return bits


def hamming(a: int, b: int) -> int:
    """两个 pHash 整数的汉明距离。"""
    return (a ^ b).bit_count()


def read_exif_date(path: str) -> Optional[str]:
    """读取 EXIF 拍摄日期，返回 YYYY-MM-DD；读不到返回 None。"""
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return None
            # 36867 = DateTimeOriginal；306 = DateTime
            raw = exif.get(36867) or exif.get(306)
            if not raw:
                return None
            text = str(raw).strip()
            # 形如 "2026:09:15 10:30:12"
            parsed = _dt.datetime.strptime(text[:19], "%Y:%m:%d %H:%M:%S")
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        return None


def fingerprint(path: str, phash_size: int = 8) -> Dict[str, object]:
    """读取单张图片，返回 ``sha1`` / ``phash`` / ``wh`` / ``decoded``。

    无法解码时 ``decoded=False``，``phash`` 为 None。
    """
    result: Dict[str, object] = {"sha1": None, "phash": None, "wh": None, "decoded": False}
    try:
        with Image.open(path) as im:
            result["sha1"] = sha1_file(path)
            result["wh"] = f"{im.width}x{im.height}"
            result["phash"] = phash(im, size=phash_size)
            result["decoded"] = True
    except Exception:
        result["sha1"] = sha1_file(path)
    return result


def group_duplicates(records: List[Dict[str, object]],
                     distance: int = 6) -> Dict[str, List[str]]:
    """对记录做重复分组。

    - 同 SHA-1 为「精确重复」组；
    - pHash 距离 ≤ ``distance`` 为「疑似相似」组。

    返回 ``{"exact": {key: [name,...]}, "similar": {key: [name,...]}}``，
    每组仅保留出现一次的代表名；调用方可据此提示保留哪一张。
    """
    exact: Dict[str, List[str]] = {}
    for r in records:
        if not r.get("sha1"):
            continue
        exact.setdefault(str(r["sha1"]), []).append(str(r["name"]))

    similar: Dict[str, List[str]] = {}
    by_name = {str(r["name"]): r for r in records if r.get("phash") is not None}
    seen: set[str] = set()
    names = list(by_name.keys())
    for i, n1 in enumerate(names):
        if n1 in seen:
            continue
        cluster = [n1]
        for n2 in names[i + 1:]:
            if n2 in seen:
                continue
            d = hamming(int(by_name[n1]["phash"]), int(by_name[n2]["phash"]))
            if d <= distance:
                cluster.append(n2)
        if len(cluster) > 1:
            key = cluster[0]
            similar[key] = cluster
            seen.update(cluster)

    return {"exact": exact, "similar": similar}


def convert_heic_to_jpg(src: str, dst_dir: str) -> Optional[str]:
    """把 HEIC/HEIF 转成 JPG 保存到 ``dst_dir``，返回新路径；不支持则返回 None。

    需要 Pillow 的 HEIF 插件（Pillow >= 10 + 对应 libheif）。
    """
    ext = os.path.splitext(src)[1].lower()
    if ext not in (".heic", ".heif"):
        return None
    base = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(dst_dir, base + ".jpg")
    try:
        with Image.open(src) as im:
            im.convert("RGB").save(dst, "JPEG", quality=90)
        return dst
    except Exception:
        return None


def apply_exif_orientation(im: Image.Image) -> Image.Image:
    """按 EXIF 方向信息校正图片旋转；无方向信息时原样返回。"""
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(im)
    except Exception:
        return im


def quality_metrics(path: str) -> Dict[str, object]:
    """读取清晰度（灰度方差）、平均亮度与横/竖/方比例标签。

    无法解码时返回 ``decoded=False`` 与空指标；不依赖 numpy，纯 Pillow 计算。
    """
    result: Dict[str, object] = {"decoded": False, "blur_score": None,
                                "brightness": None, "orientation": None}
    try:
        with Image.open(path) as im:
            im = apply_exif_orientation(im)
            gray = im.convert("L")
            w, h = gray.size
            pixels = list(gray.getdata())
            n = len(pixels)
            mean = sum(pixels) / n
            var = sum((p - mean) ** 2 for p in pixels) / n
            result.update({
                "decoded": True,
                "blur_score": round(var, 1),
                "brightness": round(mean, 1),
                "orientation": "landscape" if w > h else ("portrait" if h > w else "square"),
                "wh": f"{w}x{h}",
            })
    except Exception:
        pass
    return result


def apply_exif_orientation(im: Image.Image) -> Image.Image:
    """按 EXIF 方向信息校正图片旋转；无方向信息时原样返回。"""
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(im)
    except Exception:
        return im


def quality_metrics(path: str) -> Dict[str, object]:
    """读取清晰度（灰度方差）、平均亮度与横/竖/方比例标签。

    无法解码时返回 ``decoded=False`` 与空指标；不依赖 numpy，纯 Pillow 计算。
    """
    result: Dict[str, object] = {"decoded": False, "blur_score": None,
                                "brightness": None, "orientation": None}
    try:
        with Image.open(path) as im:
            im = apply_exif_orientation(im)
            gray = im.convert("L")
            w, h = gray.size
            pixels = list(gray.getdata())
            n = len(pixels)
            mean = sum(pixels) / n
            var = sum((p - mean) ** 2 for p in pixels) / n
            result.update({
                "decoded": True,
                "blur_score": round(var, 1),
                "brightness": round(mean, 1),
                "orientation": "landscape" if w > h else ("portrait" if h > w else "square"),
                "wh": f"{w}x{h}",
            })
    except Exception:
        pass
    return result
