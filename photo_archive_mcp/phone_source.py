# -*- coding: utf-8 -*-
"""手机 / 本地图片来源接入，按平台分派后端。

- **Windows**：通过 pywin32 的 Shell.Application 直连 MTP/WPD 便携设备（手机），
  需要 ``pywin32``（仅 Windows 可装）。
- **macOS / Linux**：没有便携设备命名空间接口，改为扫描常见本地照片目录
  （``~/Pictures``、``~/DCIM``、``~/Photos`` 等），把可导入的目录作为「设备」，
  克隆时复制文件而非 Shell.CopyHere。

任一后端都不引入平台专属强依赖；``available()`` 按当前平台与后端可用性返回。
该模块带断点续传：已存在的同名文件跳过。
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from typing import Dict, List, Optional

from . import utils

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp"}

#: macOS / Linux 常见照片目录（相对用户主目录），存在即列为可导入来源
_POSIX_PHOTO_DIRS = ["Pictures", "DCIM", "Photos", "Pictures/DCIM",
                     "Photos/DCIM", "Downloads"]


def _is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def _win_backend() -> bool:
    try:
        import win32com.client  # noqa: F401
        return True
    except Exception:
        return False


def available() -> bool:
    """当前平台是否有可用的取图后端。"""
    if _is_windows():
        return _win_backend()
    return bool(_posix_candidates())


def _posix_candidates() -> Dict[str, str]:
    """返回非 Windows 下可导入的本地照片目录：展示名 -> 绝对路径。"""
    home = os.path.expanduser("~")
    found: Dict[str, str] = {}
    for sub in _POSIX_PHOTO_DIRS:
        p = os.path.join(home, sub)
        if os.path.isdir(p):
            found[sub.replace(os.sep, "/")] = p
    return found


# --------------------------------------------------------------------------- #
# Windows MTP/WPD 后端
# --------------------------------------------------------------------------- #

def _walk(folder, path: str, out: List) -> None:
    if folder is None:
        return
    for sub in folder.Items():
        rel = path + "/" + sub.Name
        if sub.IsFolder:
            _walk(sub.GetFolder, rel, out)
        else:
            ext = "." + sub.Name.rsplit(".", 1)[-1].lower() if "." in sub.Name else ""
            if ext in IMAGE_EXTS and ".thumbnails" not in rel and "/.gs" not in rel:
                out.append((sub, rel))


def _win_list_phones() -> List[str]:
    import win32com.client
    shell = win32com.client.Dispatch("Shell.Application")
    mc = shell.Namespace(17)  # 便携设备
    return [item.Name for item in mc.Items()]


def _win_clone(phone_name: Optional[str], dest_dir: str,
               poll_seconds: float) -> Dict[str, object]:
    import win32com.client

    os.makedirs(dest_dir, exist_ok=True)
    shell = win32com.client.Dispatch("Shell.Application")
    mc = shell.Namespace(17)

    phone = None
    for item in mc.Items():
        if phone_name is None or item.Name == phone_name:
            phone = item.GetFolder
            break
    if phone is None:
        raise RuntimeError("未找到连接的手机便携设备。")

    items: List = []
    _walk(phone, "", items)

    seen: Dict = {}
    records: List[Dict[str, object]] = []
    for sub, rel in items:
        album = utils.album_of(rel)
        key = (album, sub.Name)
        if key in seen:
            continue
        seen[key] = sub
        records.append({"name": sub.Name, "path": rel,
                        "date": utils.parse_date(sub.Name), "album": album})

    dest_ns = shell.Namespace(dest_dir)
    existing = set(os.listdir(dest_dir))
    copied = 0
    failed: List[str] = []
    for r in records:
        name = r["name"]
        if name in existing:
            r["copied"] = True
            continue
        sub = seen[(r["album"], name)]
        try:
            dest_ns.CopyHere(sub, 16 | 64)
            time.sleep(poll_seconds)
            if os.path.exists(os.path.join(dest_dir, name)):
                r["copied"] = True
                copied += 1
                existing.add(name)
            else:
                r["copied"] = False
                failed.append(name)
        except Exception as e:  # noqa: BLE001
            r["copied"] = False
            failed.append(f"{name}:{e}")

    utils.write_json(os.path.join(dest_dir, "_phone_meta.json"), records)
    return {"device": phone_name or "first", "found": len(records),
            "copied_this_run": copied, "failed": len(failed),
            "failed_sample": failed[:10]}


# --------------------------------------------------------------------------- #
# macOS / Linux 本地目录后端
# --------------------------------------------------------------------------- #

def _posix_list_phones() -> List[str]:
    return sorted(_posix_candidates().keys())


def _posix_clone(source_name: Optional[str], dest_dir: str) -> Dict[str, object]:
    candidates = _posix_candidates()
    if not candidates:
        raise RuntimeError("未找到可用的本地照片目录（~Pictures、~DCIM、~Photos 等）。")
    if source_name is None:
        source_path = next(iter(candidates.values()))
    elif source_name in candidates:
        source_path = candidates[source_name]
    else:
        raise RuntimeError(f"未找到来源「{source_name}」，可用：{', '.join(candidates)}")

    os.makedirs(dest_dir, exist_ok=True)
    records: List[Dict[str, object]] = []
    existing = set(os.listdir(dest_dir))
    copied = 0
    failed: List[str] = []

    for root, _dirs, files in os.walk(source_path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMAGE_EXTS:
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, source_path).replace(os.sep, "/")
            if fname in existing:
                records.append({"name": fname, "path": rel,
                                "date": utils.parse_date(fname),
                                "album": utils.album_of(rel), "copied": True})
                continue
            target = os.path.join(dest_dir, fname)
            try:
                shutil.copy2(full, target)
                records.append({"name": fname, "path": rel,
                                "date": utils.parse_date(fname),
                                "album": utils.album_of(rel), "copied": True})
                copied += 1
                existing.add(fname)
            except Exception as e:  # noqa: BLE001
                records.append({"name": fname, "path": rel,
                                "date": utils.parse_date(fname),
                                "album": utils.album_of(rel), "copied": False})
                failed.append(f"{fname}:{e}")

    utils.write_json(os.path.join(dest_dir, "_phone_meta.json"), records)
    return {"device": source_name or next(iter(candidates)),
            "found": len(records), "copied_this_run": copied,
            "failed": len(failed), "failed_sample": failed[:10]}


# --------------------------------------------------------------------------- #
# 分派入口
# --------------------------------------------------------------------------- #

def list_phones() -> List[str]:
    """列出可导入的设备 / 本地来源名称。"""
    if _is_windows():
        return _win_list_phones() if _win_backend() else []
    return _posix_list_phones()


def clone(phone_name: Optional[str],
          dest_dir: str,
          poll_seconds: float = 0.1) -> Dict[str, object]:
    """把图片克隆到 ``dest_dir``，已存在的同名文件跳过。

    ``phone_name`` 为 None 时取第一个可用来源。返回扫描统计与失败样例。
    """
    if _is_windows():
        if not _win_backend():
            raise RuntimeError("当前环境不可用：Windows 需要安装 pywin32。请先手动把照片复制到本地文件夹。")
        return _win_clone(phone_name, dest_dir, poll_seconds)
    return _posix_clone(phone_name, dest_dir)
