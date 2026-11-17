# -*- coding: utf-8 -*-
"""photo-archive-mcp 的 MCP server（stdio 传输）。

工具对应「手机照片归档进科研知识库」的完整链路：

1. ``list_phone_devices`` / ``clone_phone_photos`` —— Windows 下从手机克隆图片（可选）。
2. ``scan_photos`` —— 扫描本地图片目录，生成元数据与缩略图。
3. ``build_selection_page`` —— 生成可勾选的单文件网页。
4. ``build_archive_plan`` —— 把勾选清单 + 当日总结/标签合并成归档计划。
5. ``archive_photos`` —— 按日期建文件夹、重命名、生成追溯清单与索引。

读图理解（判断每张图干了啥、写当日总结与标签）属于多模态判断，不在本 server 内
硬编码；上层 Agent 或人工把结论写进归档计划的 ``summary`` / ``tag`` 字段即可。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

from . import archive, config, fingerprint, ledger, phone_source, scan, suggest, webpage, utils

mcp = MCPServer("photo-archive-mcp")


@mcp.tool()
def list_phone_devices() -> Dict[str, Any]:
    """列出可导入的设备 / 本地照片来源。Windows 为 MTP 便携设备；macOS/Linux 为本地照片目录。"""
    if not phone_source.available():
        return {"available": False, "devices": [],
                "note": "当前环境不支持直连取图；请先把照片复制到本地文件夹。"}
    return {"available": True, "devices": phone_source.list_phones()}


@mcp.tool()
def clone_phone_photos(dest_dir: str, phone_name: Optional[str] = None) -> Dict[str, Any]:
    """把图片断点续传克隆到本地目录。Windows 从手机 MTP 设备取图；macOS/Linux 从本地照片目录复制。

    :param dest_dir: 本地目标目录（已存在的同名文件跳过）。
    :param phone_name: 设备 / 来源名；留空取第一个可用来源。
    """
    return phone_source.clone(phone_name, dest_dir)


@mcp.tool()
def scan_photos(source_dir: str, thumbs_dir: Optional[str] = None,
                max_side: int = 320, config_path: Optional[str] = None) -> Dict[str, Any]:
    """递归扫描本地图片目录，生成元数据、指纹与重复/损坏清单；可同时生成缩略图。

    :param source_dir: 已克隆到电脑的图片目录。
    :param thumbs_dir: 缩略图输出目录；留空则不生成缩略图。
    :param max_side: 缩略图最长边像素。
    :param config_path: 可选 JSON 配置文件路径（扩展名/跳过目录/哈希阈值等）。
    """
    cfg = config.load_config(config_path)
    records = scan.scan_folder(source_dir, cfg=cfg)
    # 相似聚类编号，供网页「按相似聚类分组」使用
    dup = fingerprint.group_duplicates(records, distance=int(cfg.get("phash_distance", 6)))
    cluster_of: Dict[str, str] = {}
    for idx, group in enumerate(dup["similar"].values(), start=1):
        for name in group:
            cluster_of[name] = f"C{idx:02d}"
    for r in records:
        r["cluster"] = cluster_of.get(str(r["name"]), "")
    if thumbs_dir:
        for r in records:
            r["source_full"] = os.path.join(source_dir, r["rel"])
        records = scan.build_thumbs(records, thumbs_dir, max_side=max_side,
                                    quality=int(cfg.get("thumb_quality", 78)),
                                    workers=int(cfg.get("concurrency", {}).get("workers", 4)))
    summary = scan.summarize(records, phash_distance=int(cfg.get("phash_distance", 6)))
    summary["records"] = records
    return summary


@mcp.tool()
def build_selection_page(records: List[Dict[str, Any]], html_path: str,
                         title: str = "实验照片挑选台",
                         experiment: str = "") -> Dict[str, Any]:
    """根据扫描记录生成单文件勾选网页（数据内联，缩略图走相对 thumbs/ 路径）。

    :param records: ``scan_photos`` 返回的 records 列表。
    :param html_path: 输出 HTML 路径；缩略图需放在同目录 ``thumbs/`` 下。
    :param experiment: 实验名，预填到网页并随清单导出。
    """
    cfg = config.load_config(None)
    vocab = list(cfg.get("tag_suggestions", []))
    suggestions = suggest.suggest_tags_for_records(records, vocab)
    for r in records:
        r["suggest"] = suggestions.get(str(r["name"]), "")
    path = webpage.build_html(records, html_path, title=title,
                              tag_suggestions=vocab, experiment=experiment)
    return {"html_path": path, "count": len(records), "vocab": vocab}


@mcp.tool()
def build_archive_plan(selected: List[Dict[str, Any]],
                       summaries: Optional[Dict[str, str]] = None,
                       tags: Optional[Dict[str, str]] = None,
                       experiment: str = "") -> Dict[str, Any]:
    """把勾选清单合并成归档计划。

    :param selected: 勾选清单条目，至少含 ``name``、``date``、``album``。
    :param summaries: ``{日期: 当日一句话总结}``，缺省用「实验记录」。
    :param tags: ``{文件名: 内容标签}``，缺省用「照片」。
    :param experiment: 实验名，归档时作为子目录分组。
    """
    plan = archive.plan_from_selection(selected, summaries=summaries, tags=tags,
                                       experiment=experiment)
    by_date: Dict[str, int] = {}
    for p in plan:
        by_date[p["date"]] = by_date.get(p["date"], 0) + 1
    return {"plan": plan, "count": len(plan), "by_date": by_date}


@mcp.tool()
def archive_photos(plan: List[Dict[str, Any]], source_dir: str, out_dir: str,
                   copy: bool = True, source_dirs: Optional[List[str]] = None,
                   incremental: bool = False,
                   figures_dir: Optional[str] = None) -> Dict[str, Any]:
    """按日期归档：建文件夹、重命名、生成追溯清单、索引与对比报告。

    :param plan: ``build_archive_plan`` 产出的计划列表。
    :param source_dir: 原始图片所在目录（主候选）。
    :param out_dir: 归档输出目录。
    :param copy: True 复制文件；False 只生成清单与索引（dry-run）。
    :param source_dirs: 多源目录候选；不传则用 ``[source_dir]``。
    :param incremental: True 跳过已在归档清单中的原始文件名。
    :param figures_dir: 若指定，``flag=paper`` 的图另存到该目录并记录用途。
    """
    return archive.archive(plan, source_dir, out_dir, copy=copy,
                            source_dirs=source_dirs, incremental=incremental,
                            figures_dir=figures_dir)


@mcp.tool()
def preview_archive_plan(plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    """dry-run 预览：只列出将要生成的目录与文件名，不触碰磁盘。

    :param plan: 归档计划列表。
    """
    tree = archive.plan_tree(plan)
    folders = sorted({t["folder"] for t in tree})
    return {"folders": len(folders), "photos": len(tree), "tree": tree}


@mcp.tool()
def lookup_archive(out_dir: str, keyword: Optional[str] = None,
                   date: Optional[str] = None, tag: Optional[str] = None,
                   original: Optional[str] = None) -> Dict[str, Any]:
    """反向检索归档清单：按归档文件名/原始文件名/日期/标签反查追溯条目。

    :param out_dir: 归档输出目录。
    :param keyword: 文件名关键词（归档名或原始名）。
    :param date: 按日期精确匹配。
    :param tag: 按标签精确匹配。
    :param original: 按原始文件名精确匹配。
    """
    rows = archive.reverse_lookup(out_dir, keyword=keyword, date=date, tag=tag, original=original)
    return {"count": len(rows), "entries": rows}


@mcp.tool()
def draft_commit_message(out_dir: str, experiment: str = "实验照片") -> Dict[str, Any]:
    """根据归档清单生成入库 commit message 草稿。

    :param out_dir: 归档输出目录（读取其中的 ``归档清单.json``）。
    :param experiment: 实验名，用于 commit 前缀。
    """
    manifest_path = os.path.join(out_dir, "归档清单.json")
    manifest = utils.read_json(manifest_path) if os.path.exists(manifest_path) else []
    message = archive.commit_message_draft(manifest, experiment=experiment)
    return {"message": message, "photos": len(manifest)}


@mcp.tool()
def inspect_archive(out_dir: str) -> Dict[str, Any]:
    """核对归档目录：文件夹数、图片数、总体积、清单与索引是否齐全。"""
    manifest_path = os.path.join(out_dir, "归档清单.json")
    index_path = os.path.join(out_dir, "照片索引.md")
    manifest = utils.read_json(manifest_path) if os.path.exists(manifest_path) else []
    folders = sorted({m["folder"] for m in manifest})
    total_bytes = 0
    for m in manifest:
        p = os.path.join(out_dir, m["folder"], m["file"])
        if os.path.exists(p):
            total_bytes += os.path.getsize(p)
    return {
        "out_dir": out_dir,
        "folders": len(folders),
        "photos": len(manifest),
        "total_size": utils.human_size(total_bytes),
        "manifest_exists": os.path.exists(manifest_path),
        "index_exists": os.path.exists(index_path),
    }


@mcp.tool()
def suggest_tags(records: List[Dict[str, Any]],
                 history_dir: Optional[str] = None) -> Dict[str, Any]:
    """按文件名/相册规则给出候选标签，并可合并历史归档用过的标签词表。

    :param records: ``scan_photos`` 返回的 records 列表。
    :param history_dir: 可选已有归档目录，读取历史标签与总结沿用。
    """
    cfg = config.load_config(None)
    base_tags = list(cfg.get("tag_suggestions", []))
    history = suggest.load_history_vocab(history_dir) if history_dir else {"tags": [], "summaries": []}
    vocab = suggest.merge_vocab(base_tags, history["tags"])
    mapping = suggest.suggest_tags_for_records(records, vocab)
    return {"suggestions": mapping, "vocab": vocab, "history_summaries": history["summaries"]}


@mcp.tool()
def export_compressed(out_dir: str, compress_dir: str,
                     max_side: Optional[int] = None,
                     quality: Optional[int] = None) -> Dict[str, Any]:
    """为归档图片另存压缩副本（沿用目录结构，原图保留不动）。

    :param out_dir: 归档输出目录。
    :param compress_dir: 压缩副本输出目录。
    :param max_side: 压缩副本最长边像素；缺省取配置 ``compress.max_side``。
    :param quality: 压缩副本 JPG 质量；缺省取配置 ``compress.quality``。
    """
    manifest = _read_manifest(out_dir)
    return archive.export_compressed(manifest, out_dir, compress_dir,
                                     max_side=max_side, quality=quality)


@mcp.tool()
def quality_filter(out_dir: str, blur_threshold: Optional[float] = None) -> Dict[str, Any]:
    """筛查失焦/过暗/过亮候选图片，返回清晰度与亮度指标清单。

    :param out_dir: 归档输出目录。
    :param blur_threshold: 灰度方差低于该值判为模糊；缺省取配置 ``quality.blur_threshold``。
    """
    manifest = _read_manifest(out_dir)
    rows = archive.quality_filter(manifest, out_dir, blur_threshold=blur_threshold)
    flagged = [r for r in rows if r["flags"]]
    return {"total": len(rows), "flagged": len(flagged), "rows": rows}


@mcp.tool()
def export_figures(out_dir: str, figures_dir: str) -> Dict[str, Any]:
    """导出标记入论文的配图清单（CSV + Markdown，自动编图号）。

    :param out_dir: 归档输出目录。
    :param figures_dir: 配图清单输出目录。
    """
    manifest = _read_manifest(out_dir)
    return archive.figures_export(manifest, figures_dir)


@mcp.tool()
def update_ledger(ledger_dir: str, experiment: str = "未分组实验",
                  source_note: str = "", committed: bool = False) -> Dict[str, Any]:
    """把当前归档清单追加进跨实验台账。

    :param ledger_dir: 台账目录（``归档台账.json`` 所在处）。
    :param experiment: 实验名。
    :param source_note: 来源说明（手机批次/目录名）。
    :param committed: 是否已入库提交。
    """
    manifest_path = os.path.join(ledger_dir, "归档清单.json")
    manifest = utils.read_json(manifest_path) if os.path.exists(manifest_path) else []
    batch = ledger.add_batch(ledger_dir, manifest, experiment=experiment,
                             source_note=source_note, committed=committed)
    return {"batch": batch, "ledger": ledger.summary(ledger_dir)}


@mcp.tool()
def query_ledger(ledger_dir: str, experiment: Optional[str] = None,
                 date: Optional[str] = None) -> Dict[str, Any]:
    """按实验名/日期检索台账条目。"""
    rows = ledger.query(ledger_dir, experiment=experiment, date=date)
    return {"count": len(rows), "entries": rows, "summary": ledger.summary(ledger_dir)}


@mcp.tool()
def target_mapping(out_dir: str, knowledge_root: str,
                   experiment: str = "未分组实验") -> Dict[str, Any]:
    """生成归档文件到知识库目标目录的映射表（只出表，不执行复制）。"""
    manifest = _read_manifest(out_dir)
    mapping = ledger.target_mapping(manifest, knowledge_root, experiment=experiment)
    return {"count": len(mapping), "mapping": mapping}


def _read_manifest(out_dir: str) -> List[Dict[str, Any]]:
    manifest_path = os.path.join(out_dir, "归档清单.json")
    return utils.read_json(manifest_path) if os.path.exists(manifest_path) else []


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
