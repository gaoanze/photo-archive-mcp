# -*- coding: utf-8 -*-
"""扫描本地图片目录，生成元数据、指纹、缩略图与汇总。

本模块只处理「已经克隆到电脑上的图片文件夹」。手机通过 MTP/WPD 直连克隆属于
Windows 专有步骤，见 ``phone_source.py``（需要 pywin32，仅 Windows 可用）。
"""
from __future__ import annotations

import collections
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from PIL import Image

from . import config, fingerprint, utils

Image.MAX_IMAGE_PIXELS = None


def _workers(cfg: Dict[str, object]) -> int:
    n = int(cfg.get("concurrency", {}).get("workers", 4))
    return max(1, n)


def _is_image(name: str, exts: set) -> bool:
    return os.path.splitext(name)[1].lower() in exts


def _cache_path(source_dir: str) -> str:
    """扫描缓存文件路径（放在源目录下的隐藏 JSON）。"""
    return os.path.join(source_dir, ".scan_cache.json")


def _load_cache(source_dir: str) -> Dict[str, Dict[str, object]]:
    path = _cache_path(source_dir)
    if os.path.exists(path):
        try:
            data = utils.read_json(path)
            if isinstance(data, dict) and isinstance(data.get("entries"), dict):
                return data["entries"]
        except Exception:
            pass
    return {}


def _save_cache(source_dir: str, entries: Dict[str, Dict[str, object]]) -> None:
    path = _cache_path(source_dir)
    try:
        utils.write_json(path, {"entries": entries})
    except Exception:
        # 缓存只是加速手段，写失败不影响扫描主流程
        pass


def _analyze(full: str, source_dir: str, phash_size: int) -> Dict[str, object]:
    """解析单张图片：指纹、日期（文件名优先，EXIF 兜底）、相册与尺寸。"""
    fname = os.path.basename(full)
    rel = os.path.relpath(full, source_dir).replace(os.sep, "/")
    size = os.path.getsize(full) if os.path.exists(full) else 0
    mtime = os.path.getmtime(full) if os.path.exists(full) else 0
    fp = fingerprint.fingerprint(full, phash_size=phash_size)

    date = utils.parse_date(fname)
    date_source = "filename"
    if date == "未知日期":
        exif_date = fingerprint.read_exif_date(full)
        if exif_date:
            date, date_source = exif_date, "exif"

    rec = {
        "name": fname,
        "rel": rel,
        "date": date,
        "date_source": date_source,
        "album": utils.album_of(rel),
        "size": size,
        "wh": fp["wh"],
        "decoded": fp["decoded"],
        "sha1": fp["sha1"],
        "phash": fp["phash"],
    }
    return {"rel": rel, "size": size, "mtime": mtime, "record": rec}


def scan_folder(source_dir: str,
                skip_cache: bool = True,
                cfg: Optional[Dict[str, object]] = None,
                progress: Optional[object] = None,
                use_cache: bool = True) -> List[Dict[str, object]]:
    """递归扫描目录，返回每条图片的元数据记录。

    返回字段：``name`` / ``date`` / ``date_source`` / ``album`` / ``rel`` /
    ``size`` / ``wh`` / ``decoded`` / ``sha1`` / ``phash``。
    同名文件按路径去重，保留首个出现。

    :param progress: 可选回调 ``fn(done: int, total: int, name: str)``，用于进度上报。
    :param use_cache: 是否启用扫描缓存；按相对路径 + mtime + size 判定，
        未变化的文件复用上次的指纹/日期/尺寸，避免重复解码与哈希。
    """
    cfg = cfg or config.load_config(None)
    exts = {e.lower() for e in cfg.get("image_exts", config.IMAGE_EXTS)}
    skip_marks = tuple(cfg.get("skip_dir_marks", config.SKIP_DIR_MARKS))
    phash_size = int(cfg.get("phash_size", config.PHASH_SIZE))
    workers = _workers(cfg)
    if use_cache and not cfg.get("cache", {}).get("enabled", True):
        use_cache = False

    # 先收集候选文件，便于进度计数
    candidates: List[str] = []
    for root, dirs, files in os.walk(source_dir):
        if skip_cache:
            dirs[:] = [d for d in dirs if not any(m in d for m in skip_marks)]
        for fname in files:
            if _is_image(fname, exts):
                candidates.append(os.path.join(root, fname))

    cache = _load_cache(source_dir) if use_cache else {}
    new_cache: Dict[str, Dict[str, object]] = {}
    records: List[Dict[str, object]] = []
    seen = set()
    total = len(candidates)

    # 先按同名去重，保留首个出现的路径
    ordered: List[str] = []
    for full in candidates:
        fname = os.path.basename(full)
        if fname in seen:
            continue
        seen.add(fname)
        ordered.append(full)

    # 区分可复用缓存与需重新解析的文件
    stale: List[str] = []
    for full in ordered:
        rel = os.path.relpath(full, source_dir).replace(os.sep, "/")
        size = os.path.getsize(full) if os.path.exists(full) else 0
        mtime = os.path.getmtime(full) if os.path.exists(full) else 0
        cached = cache.get(rel)
        if (cached and cached.get("size") == size and
                float(cached.get("mtime", 0)) == mtime):
            rec = dict(cached["record"])
            rec["size"] = size
            new_cache[rel] = {"size": size, "mtime": mtime, "record": rec}
            records.append(rec)
        else:
            stale.append(full)

    # 并发解析未命中缓存的文件
    done = total - len(stale)
    if stale:
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_analyze, full, source_dir, phash_size): full
                           for full in stale}
                for fut in as_completed(futures):
                    entry = fut.result()
                    new_cache[entry["rel"]] = {"size": entry["size"],
                                               "mtime": entry["mtime"],
                                               "record": entry["record"]}
                    records.append(entry["record"])
                    done += 1
                    if progress:
                        progress(done, total, entry["record"]["name"])
        else:
            for full in stale:
                entry = _analyze(full, source_dir, phash_size)
                new_cache[entry["rel"]] = {"size": entry["size"],
                                           "mtime": entry["mtime"],
                                           "record": entry["record"]}
                records.append(entry["record"])
                done += 1
                if progress:
                    progress(done, total, entry["record"]["name"])

    if use_cache:
        _save_cache(source_dir, new_cache)
    records.sort(key=lambda r: (r["date"], r["name"]))
    return records


def _render_thumb(r: Dict[str, object], i: int, thumbs_dir: str,
                  max_side: int, quality: int) -> Dict[str, object]:
    src = r.get("source_full")
    if not src:
        rel = str(r.get("rel") or "")
        if rel:
            src = os.path.join(os.path.dirname(thumbs_dir), rel)
    thumb_name = f"t_{i:05d}.jpg"
    thumb_path = os.path.join(thumbs_dir, thumb_name)
    got = False
    if src and os.path.exists(src):
        try:
            with Image.open(src) as im:
                im.thumbnail((max_side, max_side))
                im.convert("RGB").save(thumb_path, "JPEG", quality=quality)
            got = True
        except Exception:
            got = False
    rec = dict(r)
    rec["thumb"] = thumb_name if got else ""
    return rec


def build_thumbs(records: List[Dict[str, object]],
                 thumbs_dir: str,
                 max_side: int = 320,
                 quality: int = 78,
                 workers: int = 4) -> List[Dict[str, object]]:
    """为可解码图片生成缩略图，回填 ``thumb`` 字段（相对 thumbs_dir 的文件名）。"""
    os.makedirs(thumbs_dir, exist_ok=True)
    workers = max(1, int(workers))
    if workers > 1 and len(records) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda args: _render_thumb(*args),
                                 [(r, i, thumbs_dir, max_side, quality)
                                  for i, r in enumerate(records, start=1)]))
    return [_render_thumb(r, i, thumbs_dir, max_side, quality)
            for i, r in enumerate(records, start=1)]


def summarize(records: List[Dict[str, object]],
              phash_distance: int = config.PHASH_DISTANCE) -> Dict[str, object]:
    """按日期、相册、可解码情况汇总，并给出重复分组、损坏清单与比例/体积统计。"""
    by_date = collections.Counter(r["date"] for r in records)
    by_album = collections.Counter(r["album"] for r in records)
    decoded = sum(1 for r in records if r["decoded"])
    duplicates = fingerprint.group_duplicates(records, distance=phash_distance)

    broken = [{"name": r["name"], "rel": r["rel"], "size": r["size"]}
              for r in records if not r["decoded"]]

    exact_groups = [v for v in duplicates["exact"].values() if len(v) > 1]
    similar_groups = [v for v in duplicates["similar"].values() if len(v) > 1]

    # 横 / 竖 / 方比例分布（依据宽高比；缺尺寸记为未知）
    orientation = collections.Counter()
    by_album_bytes: Dict[str, int] = collections.Counter()

    def _parse_wh(wh: object):
        if isinstance(wh, (list, tuple)) and len(wh) == 2 and wh[0] and wh[1]:
            return int(wh[0]), int(wh[1])
        if isinstance(wh, str) and "x" in wh:
            parts = wh.lower().split("x")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return int(parts[0]), int(parts[1])
        return None

    for r in records:
        dims = _parse_wh(r.get("wh"))
        if dims:
            w, h = dims
            if w > h * 1.05:
                orientation["landscape"] += 1
            elif h > w * 1.05:
                orientation["portrait"] += 1
            else:
                orientation["square"] += 1
        else:
            orientation["unknown"] += 1
        by_album_bytes[r["album"]] += int(r["size"] or 0)

    return {
        "total": len(records),
        "decoded": decoded,
        "undecoded": len(records) - decoded,
        "by_date": dict(sorted(by_date.items())),
        "by_album": dict(by_album.most_common()),
        "total_bytes": sum(int(r["size"] or 0) for r in records),
        "by_album_bytes": dict(by_album_bytes.most_common()),
        "orientation": dict(orientation),
        "broken": broken,
        "duplicates": {
            "exact_groups": exact_groups,
            "similar_groups": similar_groups,
            "exact_count": sum(len(g) - 1 for g in exact_groups),
            "similar_count": sum(len(g) - 1 for g in similar_groups),
        },
    }
