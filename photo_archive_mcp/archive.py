# -*- coding: utf-8 -*-
"""按日期归档：建文件夹、重命名、生成追溯清单、索引与对比报告。

命名规则（与用户确认的口径一致）：

- 文件夹：``YYYY-MM-DD-当日一句话总结``
- 图片：``文件夹名-内容标签-编号.扩展名``

标签/当日总结由上层（多模态读图或人工）写进「归档计划」JSON，本模块只负责
确定性地落地文件并保留原始文件名追溯关系。
"""
from __future__ import annotations

import collections
import datetime as _dt
import os
import shutil
from typing import Dict, List, Optional

from . import config, utils


def _group_by_date(plan: List[Dict[str, object]]) -> "collections.OrderedDict[str, List[Dict[str, object]]]":
    grouped: "collections.OrderedDict[str, List[Dict[str, object]]]" = collections.OrderedDict()
    for item in sorted(plan, key=lambda x: (str(x["date"]), str(x["name"]))):
        grouped.setdefault(str(item["date"]), []).append(item)
    return grouped


def _resolve_source(item: Dict[str, object], source_dirs: List[str]) -> Optional[str]:
    """按候选源目录定位源文件；返回首个存在的完整路径，找不到返回 None。"""
    name = str(item["name"])
    rel = str(item.get("rel") or "")
    for base in source_dirs:
        if rel:
            cand = os.path.join(base, rel)
            if os.path.exists(cand):
                return cand
        cand = os.path.join(base, name)
        if os.path.exists(cand):
            return cand
    return None


def plan_tree(plan: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """dry-run：只生成将要落地的目录/文件名，不碰磁盘。

    返回每条：``folder`` / ``new_name`` / ``original`` / ``date`` / ``tag`` / ``flag``。
    """
    grouped = _group_by_date(plan)
    tree: List[Dict[str, object]] = []
    for date, items in grouped.items():
        summary = utils.safe_name(str(items[0].get("summary") or "实验记录"))
        folder_name = f"{date}-{summary}"
        used_names: set[str] = set()
        for i, item in enumerate(items, start=1):
            ext = os.path.splitext(str(item["name"]))[1]
            tag = utils.safe_name(str(item.get("tag") or "照片"))
            new_name = f"{folder_name}-{tag}-{i:02d}{ext}"
            # 防重：同目录同名时追加序号后缀
            n = 2
            while new_name in used_names:
                new_name = f"{folder_name}-{tag}-{i:02d}-{n}{ext}"
                n += 1
            used_names.add(new_name)
            tree.append({
                "folder": folder_name,
                "new_name": new_name,
                "original": str(item["name"]),
                "date": date,
                "tag": tag,
                "flag": item.get("flag", ""),
            })
    return tree


def archive(plan: List[Dict[str, object]],
            source_dir: str,
            out_dir: str,
            copy: bool = True,
            source_dirs: Optional[List[str]] = None,
            incremental: bool = False,
            figures_dir: Optional[str] = None) -> Dict[str, object]:
    """落地归档。

    ``plan`` 每条字段：``name``（源文件名）、``date``、``summary``（当日总结）、
    ``tag``（内容标签）、``album``（可选）、``rel``（可选，源相对路径）、
    ``flag``（可选：``paper`` 入论文 / ``archive`` 仅留档 / 空）。

    - ``copy=True`` 复制到 ``out_dir``；``False`` 仅生成清单与索引、不动源文件（dry-run）。
    - ``source_dirs``：多源目录候选；不传则用 ``[source_dir]``。
    - ``incremental=True``：已存在于归档清单中的原始文件名不再复制（增量归档）。
    - ``figures_dir``：若指定，``flag=paper`` 的图另存到该目录并记录用途。
    返回追溯清单、对比报告与统计信息。
    """
    source_dirs = source_dirs or [source_dir]
    prior_names: set[str] = set()
    kept: List[Dict[str, object]] = []
    if incremental:
        prior_names = _existing_originals(out_dir)

    # 增量归档保留已有目录与图片；非增量才整体清空重建
    if copy and os.path.exists(out_dir) and not incremental:
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    grouped = _group_by_date(plan)
    manifest: List[Dict[str, object]] = []
    missing: List[str] = []
    skipped_existing: List[str] = []
    conflicts: List[Dict[str, str]] = []
    folders: List[str] = []
    figures: List[Dict[str, object]] = []

    for date, items in grouped.items():
        summary = utils.safe_name(str(items[0].get("summary") or "实验记录"))
        experiment = utils.safe_name(str(items[0].get("experiment") or ""))
        folder_name = f"{date}-{summary}"
        # 有实验名时，输出目录下再分一层实验子目录
        rel_folder = os.path.join(experiment, folder_name) if experiment else folder_name
        folders.append(rel_folder)
        folder_path = os.path.join(out_dir, rel_folder)
        os.makedirs(folder_path, exist_ok=True)
        used_names: set[str] = set()
        for i, item in enumerate(items, start=1):
            name = str(item["name"])
            ext = os.path.splitext(name)[1]
            tag = utils.safe_name(str(item.get("tag") or "照片"))
            new_name = f"{folder_name}-{tag}-{i:02d}{ext}"
            n = 2
            while new_name in used_names:
                new_name = f"{folder_name}-{tag}-{i:02d}-{n}{ext}"
                n += 1
            used_names.add(new_name)

            if incremental and name in prior_names:
                skipped_existing.append(name)
                continue

            src = _resolve_source(item, source_dirs)
            dst = os.path.join(folder_path, new_name)
            if not src:
                missing.append(name)
                continue
            if os.path.exists(dst):
                conflicts.append({"folder": rel_folder, "file": new_name, "original": name})
                continue
            if copy:
                shutil.copy2(src, dst)

            entry = {
                "folder": rel_folder,
                "file": new_name,
                "original": name,
                "album": item.get("album", ""),
                "date": date,
                "tag": tag,
                "flag": item.get("flag", ""),
                "experiment": experiment,
            }
            manifest.append(entry)

            if item.get("flag") == "paper" and figures_dir:
                os.makedirs(figures_dir, exist_ok=True)
                fig_dst = os.path.join(figures_dir, new_name)
                if copy:
                    shutil.copy2(src, fig_dst)
                figures.append({"file": new_name, "original": name, "date": date,
                                "tag": tag, "folder": rel_folder, "experiment": experiment})

    manifest_path = os.path.join(out_dir, "归档清单.json")
    if incremental:
        # 保留上一轮已归档、本轮跳过的条目，避免清单被清空
        old_rows = utils.read_json(manifest_path) if os.path.exists(manifest_path) else []
        kept = [m for m in old_rows if str(m.get("original")) in prior_names]
        manifest = kept + manifest
    utils.write_json(manifest_path, manifest)

    index_path = os.path.join(out_dir, "照片索引.md")
    _write_index(index_path, manifest, folders)

    report = _build_report(plan, manifest, missing, skipped_existing, conflicts, figures)
    report_path = os.path.join(out_dir, "归档对比报告.json")
    utils.write_json(report_path, report)

    mapping_path = os.path.join(out_dir, "归档对照表.json")
    utils.write_json(mapping_path, mapping_table(manifest))
    rollback_path = write_rollback_manifest(out_dir, manifest)

    if figures_dir and figures:
        utils.write_json(os.path.join(figures_dir, "figures_清单.json"), figures)

    return {
        "out_dir": out_dir,
        "folders": len(folders),
        "photos": len(manifest) - len(kept) if incremental else len(manifest),
        "manifest_total": len(manifest),
        "missing": len(missing),
        "missing_names": missing[:20],
        "skipped_existing": len(skipped_existing),
        "conflicts": conflicts,
        "figures": len(figures),
        "manifest_path": manifest_path,
        "index_path": index_path,
        "report_path": report_path,
        "mapping_path": mapping_path,
        "rollback_path": rollback_path,
        "report": report,
    }


def _existing_originals(out_dir: str) -> set[str]:
    """读取已有归档清单里的原始文件名，用于增量判断。"""
    prior: set[str] = set()
    manifest_path = os.path.join(out_dir, "归档清单.json")
    if os.path.exists(manifest_path):
        try:
            for m in utils.read_json(manifest_path):
                prior.add(str(m.get("original")))
        except Exception:
            pass
    return prior


def _build_report(plan, manifest, missing, skipped_existing, conflicts, figures) -> Dict[str, object]:
    by_date_plan = collections.Counter(str(i["date"]) for i in plan)
    by_date_arch = collections.Counter(str(m["date"]) for m in manifest)
    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "plan_total": len(plan),
        "archived_total": len(manifest),
        "missing_total": len(missing),
        "skipped_existing_total": len(skipped_existing),
        "conflict_total": len(conflicts),
        "figures_total": len(figures),
        "by_date_plan": dict(sorted(by_date_plan.items())),
        "by_date_archived": dict(sorted(by_date_arch.items())),
        "missing_names": missing[:50],
        "conflicts": conflicts,
        "figures": figures,
    }


def reverse_lookup(out_dir: str, keyword: Optional[str] = None,
                   date: Optional[str] = None, tag: Optional[str] = None,
                   original: Optional[str] = None) -> List[Dict[str, object]]:
    """反向检索：按归档文件名 / 原始文件名 / 日期 / 标签反查清单条目。

    读取 ``out_dir/归档清单.json``，任一条件命中即返回；不传条件返回全部。
    """
    manifest_path = os.path.join(out_dir, "归档清单.json")
    if not os.path.exists(manifest_path):
        return []
    rows = utils.read_json(manifest_path)
    result: List[Dict[str, object]] = []
    for m in rows:
        if original and str(m.get("original")) != original:
            continue
        if date and str(m.get("date")) != date:
            continue
        if tag and str(m.get("tag")) != tag:
            continue
        if keyword:
            kw = keyword.lower()
            if not (kw in str(m.get("file", "")).lower() or kw in str(m.get("original", "")).lower()):
                continue
        result.append(m)
    return result


def commit_message_draft(manifest: List[Dict[str, object]], experiment: str = "实验照片") -> str:
    """根据归档清单生成入库 commit message 草稿。"""
    by_date = collections.OrderedDict()
    for m in sorted(manifest, key=lambda x: (x["date"], x["file"])):
        by_date.setdefault(str(m["date"]), []).append(m["file"])
    lines = [f"chore({experiment}): 归档 {len(manifest)} 张实验照片"]
    for date, files in by_date.items():
        lines.append(f"- {date}：{len(files)} 张")
    return "\n".join(lines)


def mapping_table(manifest: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """生成「原始文件名 ↔ 归档文件名」对照表，供核对与回滚使用。"""
    return [{
        "original": m.get("original", ""),
        "file": m.get("file", ""),
        "folder": m.get("folder", ""),
        "date": m.get("date", ""),
        "tag": m.get("tag", ""),
        "album": m.get("album", ""),
    } for m in manifest]


def write_rollback_manifest(out_dir: str, manifest: List[Dict[str, object]]) -> str:
    """写出回滚清单：记录每条归档文件对应的源文件与目标路径。

    回滚时按此清单删除已复制的归档文件（源克隆目录不受影响）。
    返回回滚清单 JSON 路径。
    """
    rollback = [{
        "archive_path": os.path.join(m.get("folder", ""), m.get("file", "")),
        "original": m.get("original", ""),
        "date": m.get("date", ""),
    } for m in manifest]
    path = os.path.join(out_dir, "回滚清单.json")
    utils.write_json(path, rollback)
    return path


def export_compressed(manifest: List[Dict[str, object]], out_dir: str,
                      compress_dir: str, max_side: Optional[int] = None,
                      quality: Optional[int] = None,
                      cfg: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """为归档图片另存压缩副本到 ``compress_dir``，返回压缩前后体积统计。

    压缩副本沿用归档目录结构；原始大图保留在归档目录不动。
    ``max_side`` / ``quality`` 缺省时取配置 ``compress`` 分组。
    """
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    cfg = cfg or config.load_config(None)
    compress_cfg = cfg.get("compress", {})
    if max_side is None:
        max_side = int(compress_cfg.get("max_side", 1600))
    if quality is None:
        quality = int(compress_cfg.get("quality", 82))
    os.makedirs(compress_dir, exist_ok=True)
    rows: List[Dict[str, object]] = []
    src_bytes = dst_bytes = 0
    for m in manifest:
        src = os.path.join(out_dir, m["folder"], m["file"])
        if not os.path.exists(src):
            continue
        dst = os.path.join(compress_dir, m["folder"], m["file"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            with Image.open(src) as im:
                from . import fingerprint as fp_mod
                im = fp_mod.apply_exif_orientation(im)
                im.thumbnail((max_side, max_side))
                im.convert("RGB").save(dst, "JPEG", quality=quality)
            s0 = os.path.getsize(src)
            s1 = os.path.getsize(dst)
            src_bytes += s0
            dst_bytes += s1
            rows.append({"file": m["file"], "folder": m["folder"],
                         "original": m["original"], "src_bytes": s0, "dst_bytes": s1})
        except Exception:
            continue
    ratio = round(dst_bytes / src_bytes, 3) if src_bytes else 0
    return {"files": len(rows), "src_bytes": src_bytes, "dst_bytes": dst_bytes,
            "ratio": ratio, "rows": rows}


def quality_filter(manifest: List[Dict[str, object]], out_dir: str,
                   blur_threshold: Optional[float] = None,
                   brightness_range: Optional[tuple] = None,
                   cfg: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
    """筛查失焦 / 过暗 / 过亮候选图片，返回带质量指标的清单。

    指标纯 Pillow 计算（灰度方差为清晰度分）；低于阈值或亮度越界即标记。
    阈值缺省时取配置 ``quality`` 分组。
    """
    from . import fingerprint as fp_mod
    cfg = cfg or config.load_config(None)
    q = cfg.get("quality", {})
    if blur_threshold is None:
        blur_threshold = float(q.get("blur_threshold", 100.0))
    if brightness_range is None:
        brightness_range = (int(q.get("brightness_min", 30)),
                            int(q.get("brightness_max", 235)))
    result: List[Dict[str, object]] = []
    for m in manifest:
        src = os.path.join(out_dir, m["folder"], m["file"])
        if not os.path.exists(src):
            continue
        metrics = fp_mod.quality_metrics(src)
        if not metrics["decoded"]:
            continue
        flags: List[str] = []
        if metrics["blur_score"] is not None and metrics["blur_score"] < blur_threshold:
            flags.append("模糊")
        if metrics["brightness"] is not None:
            lo, hi = brightness_range
            if metrics["brightness"] < lo:
                flags.append("过暗")
            elif metrics["brightness"] > hi:
                flags.append("过亮")
        result.append({
            "file": m["file"], "folder": m["folder"], "original": m["original"],
            "blur_score": metrics["blur_score"], "brightness": metrics["brightness"],
            "orientation": metrics["orientation"], "wh": metrics.get("wh"),
            "flags": flags,
        })
    return result


def figures_export(manifest: List[Dict[str, object]],
                   figures_dir: str) -> Dict[str, object]:
    """导出标记 ``paper`` 的论文配图清单（CSV 与 Markdown）。

    返回清单条目与写出的文件路径；图号按日期+标签顺序编号。
    """
    papers = [m for m in manifest if m.get("flag") == "paper"]
    papers.sort(key=lambda x: (str(x["date"]), str(x["file"])))
    rows: List[Dict[str, object]] = []
    for i, m in enumerate(papers, start=1):
        rows.append({
            "figure_no": f"Fig.{i:02d}",
            "date": m["date"],
            "folder": m["folder"],
            "file": m["file"],
            "original": m["original"],
            "tag": m["tag"],
            "experiment": m.get("experiment", ""),
        })

    os.makedirs(figures_dir, exist_ok=True)
    csv_path = os.path.join(figures_dir, "论文配图清单.csv")
    md_path = os.path.join(figures_dir, "论文配图清单.md")

    import csv
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["图号", "日期", "实验", "标签", "归档文件", "原始文件名", "目录"])
        for r in rows:
            writer.writerow([r["figure_no"], r["date"], r["experiment"], r["tag"],
                             r["file"], r["original"], r["folder"]])

    lines = ["# 论文配图清单\n", f"共 {len(rows)} 张\n",
             "| 图号 | 日期 | 实验 | 标签 | 归档文件 | 原始文件名 |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['figure_no']} | {r['date']} | {r['experiment']} | "
                     f"{r['tag']} | {r['file']} | {r['original']} |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"count": len(rows), "csv_path": csv_path, "md_path": md_path, "rows": rows}


def _write_index(index_path: str,
                 manifest: List[Dict[str, object]],
                 folders: List[str]) -> None:
    by_folder: "collections.OrderedDict[str, List[Dict[str, object]]]" = collections.OrderedDict()
    for m in sorted(manifest, key=lambda x: (x["folder"], x["file"])):
        by_folder.setdefault(m["folder"], []).append(m)

    lines: List[str] = []
    lines.append("# 实验照片归档索引\n")
    lines.append(f"**归档日期**：{_dt.date.today().isoformat()}　"
                 f"**照片总数**：{len(manifest)}　**日期批次**：{len(folders)}\n")
    lines.append("命名规则：`日期-当日总结-内容标签-编号.扩展名`；原始文件名见各条目，便于追溯。\n")
    lines.append("---\n")
    for folder, items in by_folder.items():
        lines.append(f"## {folder}（{len(items)} 张）\n")
        lines.append("| 序号 | 文件 | 内容标签 | 标记 | 来源相册 | 原始文件名 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for i, m in enumerate(items, start=1):
            flag = m.get("flag", "") or ""
            lines.append(f"| {i:02d} | {m['file']} | {m['tag']} | {flag} | {m['album']} | {m['original']} |")
        lines.append("")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def plan_from_selection(selected: List[Dict[str, object]],
                        summaries: Optional[Dict[str, str]] = None,
                        tags: Optional[Dict[str, str]] = None,
                        experiment: str = "") -> List[Dict[str, object]]:
    """把勾选清单与（可选的）当日总结、逐张标签合并成归档计划。

    - ``selected``：勾选清单条目，至少含 ``name``、``date``、``album``；
      可选 ``tag``、``flag``、``rel``、``experiment``。
    - ``summaries``：``{date: 当日总结}``，缺省时用 ``实验记录``。
    - ``tags``：``{文件名: 内容标签}``，缺省时取条目自带 ``tag``，再用 ``照片``。
    - ``experiment``：实验名；缺省取条目自带 ``experiment``，再留空。
    """
    summaries = summaries or {}
    tags = tags or {}
    plan: List[Dict[str, object]] = []
    for s in selected:
        name = str(s["name"])
        date = str(s.get("date") or utils.parse_date(name))
        plan.append({
            "name": name,
            "date": date,
            "album": s.get("album", ""),
            "rel": s.get("rel", ""),
            "summary": summaries.get(date, "实验记录"),
            "tag": tags.get(name, s.get("tag") or "照片"),
            "flag": s.get("flag", ""),
            "experiment": s.get("experiment") or experiment,
        })
    return plan


def _write_index(index_path: str,
                 manifest: List[Dict[str, object]],
                 folders: List[str]) -> None:
    by_folder: "collections.OrderedDict[str, List[Dict[str, object]]]" = collections.OrderedDict()
    for m in sorted(manifest, key=lambda x: (x["folder"], x["file"])):
        by_folder.setdefault(m["folder"], []).append(m)

    lines: List[str] = []
    lines.append("# 实验照片归档索引\n")
    lines.append(f"**归档日期**：{_dt.date.today().isoformat()}　"
                 f"**照片总数**：{len(manifest)}　**日期批次**：{len(folders)}\n")
    lines.append("命名规则：`日期-当日总结-内容标签-编号.扩展名`；原始文件名见各条目，便于追溯。\n")
    lines.append("---\n")
    for folder, items in by_folder.items():
        lines.append(f"## {folder}（{len(items)} 张）\n")
        lines.append("| 序号 | 文件 | 内容标签 | 标记 | 来源相册 | 原始文件名 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for i, m in enumerate(items, start=1):
            flag = m.get("flag", "") or ""
            lines.append(f"| {i:02d} | {m['file']} | {m['tag']} | {flag} | {m['album']} | {m['original']} |")
        lines.append("")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def plan_from_selection(selected: List[Dict[str, object]],
                        summaries: Optional[Dict[str, str]] = None,
                        tags: Optional[Dict[str, str]] = None,
                        experiment: str = "") -> List[Dict[str, object]]:
    """把勾选清单与（可选的）当日总结、逐张标签合并成归档计划。

    - ``selected``：勾选清单条目，至少含 ``name``、``date``、``album``；
      可选 ``tag``、``flag``、``rel``、``experiment``。
    - ``summaries``：``{date: 当日总结}``，缺省时用 ``实验记录``。
    - ``tags``：``{文件名: 内容标签}``，缺省时取条目自带 ``tag``，再用 ``照片``。
    - ``experiment``：实验名；缺省取条目自带 ``experiment``，再留空。
    """
    summaries = summaries or {}
    tags = tags or {}
    plan: List[Dict[str, object]] = []
    for s in selected:
        name = str(s["name"])
        date = str(s.get("date") or utils.parse_date(name))
        plan.append({
            "name": name,
            "date": date,
            "album": s.get("album", ""),
            "rel": s.get("rel", ""),
            "summary": summaries.get(date, "实验记录"),
            "tag": tags.get(name, s.get("tag") or "照片"),
            "flag": s.get("flag", ""),
            "experiment": s.get("experiment") or experiment,
        })
    return plan
