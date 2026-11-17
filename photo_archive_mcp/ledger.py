# -*- coding: utf-8 -*-
"""跨实验归档台账：记录每次归档的批次、日期、张数、体积与入库状态，支持检索。

台账是一个 JSON 文件，按实验名聚合；每次归档后追加一条批次记录，
不修改原始归档目录。
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Dict, List, Optional

from . import utils


def _ledger_path(ledger_dir: str) -> str:
    return os.path.join(ledger_dir, "归档台账.json")


def load_ledger(ledger_dir: str) -> Dict[str, Any]:
    """读取台账；不存在时返回空结构。"""
    path = _ledger_path(ledger_dir)
    if os.path.exists(path):
        try:
            data = utils.read_json(path)
            if isinstance(data, dict):
                data.setdefault("experiments", {})
                return data
        except Exception:
            pass
    return {"experiments": {}, "updated_at": None}


def add_batch(ledger_dir: str, manifest: List[Dict[str, Any]],
              experiment: str = "未分组实验",
              source_note: str = "",
              committed: bool = False) -> Dict[str, Any]:
    """把一次归档清单追加为台账批次。

    :param manifest: 归档清单条目。
    :param experiment: 实验名。
    :param source_note: 来源说明（如手机批次、目录名）。
    :param committed: 是否已入库提交。
    """
    ledger = load_ledger(ledger_dir)
    exp = ledger["experiments"].setdefault(experiment, {"batches": []})

    by_date: Dict[str, int] = {}
    total_bytes = 0
    for m in manifest:
        by_date[str(m["date"])] = by_date.get(str(m["date"]), 0) + 1
        total_bytes += int(m.get("size") or 0)

    batch = {
        "archived_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source_note": source_note,
        "photos": len(manifest),
        "total_bytes": total_bytes,
        "by_date": dict(sorted(by_date.items())),
        "committed": committed,
        "files": [{"file": m["file"], "original": m["original"],
                   "date": m["date"], "tag": m["tag"]} for m in manifest],
    }
    exp["batches"].append(batch)
    ledger["updated_at"] = batch["archived_at"]

    os.makedirs(ledger_dir, exist_ok=True)
    utils.write_json(_ledger_path(ledger_dir), ledger)
    return batch


def query(ledger_dir: str, experiment: Optional[str] = None,
          date: Optional[str] = None) -> List[Dict[str, Any]]:
    """按实验名 / 日期检索台账条目（文件级）。"""
    ledger = load_ledger(ledger_dir)
    out: List[Dict[str, Any]] = []
    for exp_name, exp in ledger["experiments"].items():
        if experiment and exp_name != experiment:
            continue
        for batch in exp.get("batches", []):
            for f in batch.get("files", []):
                if date and f["date"] != date:
                    continue
                out.append({"experiment": exp_name, "batch_at": batch["archived_at"],
                            "committed": batch["committed"], **f})
    return out


def summary(ledger_dir: str) -> Dict[str, Any]:
    """台账汇总：各实验批次、张数、日期覆盖、入库状态。"""
    ledger = load_ledger(ledger_dir)
    result: Dict[str, Any] = {"experiments": {}, "updated_at": ledger.get("updated_at")}
    for exp_name, exp in ledger["experiments"].items():
        batches = exp.get("batches", [])
        photos = sum(b["photos"] for b in batches)
        dates = sorted({d for b in batches for d in b.get("by_date", {})})
        committed = all(b.get("committed") for b in batches) if batches else False
        result["experiments"][exp_name] = {
            "batches": len(batches), "photos": photos,
            "dates": dates, "all_committed": committed,
        }
    return result


def target_mapping(manifest: List[Dict[str, Any]],
                   knowledge_root: str,
                   experiment: str = "未分组实验") -> List[Dict[str, Any]]:
    """生成「归档文件 → 知识库目标路径」映射表（不执行复制）。

    目标结构：``<knowledge_root>/experiments/<experiment>/<日期文件夹>/<文件名>``。
    """
    mapping: List[Dict[str, Any]] = []
    for m in manifest:
        rel = os.path.join("experiments", experiment, m["folder"], m["file"])
        mapping.append({
            "source": os.path.join(m["folder"], m["file"]),
            "target": os.path.join(knowledge_root, rel),
            "original": m["original"],
            "date": m["date"],
            "tag": m["tag"],
        })
    return mapping
