# -*- coding: utf-8 -*-
"""命令行演示：不启动 MCP 客户端，直接跑通「扫描 → 勾选网页 → 归档」链路。

用法示例：

    python examples/cli_demo.py --source ./photos --out ./archive_ready
    python examples/cli_demo.py --source ./photos --out ./archive_ready \
        --plan ./archive_plan.json
    python examples/cli_demo.py --source ./photos --out ./archive_ready \
        --dry-run --incremental --figures ./figures

``--plan`` 为可选归档计划 JSON（条目含 ``name`` / ``date`` / ``summary`` /
``tag`` / ``album`` / ``flag``）。不提供时，当日总结与标签先用占位值生成计划，
可在网页勾选后再按真实读图理解回填。

所有路径由命令行参数给定，脚本不写入任何固定本机路径。
"""
import argparse
import os
import sys

# 以脚本位置定位项目根，便于未安装包时直接运行
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from photo_archive_mcp import archive, config, ledger, scan, suggest, utils, webpage


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="实验照片归档链路命令行演示")
    p.add_argument("--source", required=True, help="待归档图片所在目录")
    p.add_argument("--out", required=True, help="归档输出目录")
    p.add_argument("--plan", help="可选：归档计划 JSON 路径")
    p.add_argument("--html", help="可选：勾选网页输出路径，默认 <out>/挑选台.html")
    p.add_argument("--thumbs", help="可选：缩略图目录，默认 <out>/thumbs")
    p.add_argument("--figures", help="可选：入论文图片另存目录")
    p.add_argument("--experiment", default="", help="可选：实验名，归档时作为子目录分组")
    p.add_argument("--dry-run", action="store_true", help="只生成清单/索引，不复制文件")
    p.add_argument("--incremental", action="store_true", help="跳过已归档的原始文件名")
    p.add_argument("--lookup", help="可选：按关键词反向检索已有归档清单")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    source = os.path.abspath(args.source)
    out = os.path.abspath(args.out)
    html_path = os.path.abspath(args.html or os.path.join(out, "挑选台.html"))
    thumbs_dir = os.path.abspath(args.thumbs or os.path.join(out, "thumbs"))
    figures_dir = os.path.abspath(args.figures) if args.figures else None

    if not os.path.isdir(source):
        print(f"源目录不存在: {source}")
        return 2

    # 0. 反向检索（针对已有归档目录，不做扫描）
    if args.lookup:
        rows = archive.reverse_lookup(out, keyword=args.lookup)
        print(f"检索命中 {len(rows)} 条")
        for m in rows:
            print("   ", m["file"], "<-", m["original"])
        return 0

    # 1. 扫描
    records = scan.scan_folder(source)
    for r in records:
        r["source_full"] = os.path.join(source, r["rel"])
    records = scan.build_thumbs(records, thumbs_dir)
    summary = scan.summarize(records)
    print(f"[1] 扫描: {summary['total']} 张, 可解码 {summary['decoded']}, "
          f"日期组 {len(summary['by_date'])}, 损坏 {len(summary['broken'])}, "
          f"精确重复 {summary['duplicates']['exact_count']}, 相似 {summary['duplicates']['similar_count']}")

    # 2. 勾选网页（带建议标签与实验名预填）
    cfg = config.load_config(None)
    vocab = list(cfg.get("tag_suggestions", []))
    suggestions = suggest.suggest_tags_for_records(records, vocab)
    for r in records:
        r["suggest"] = suggestions.get(str(r["name"]), "")
    webpage.build_html(records, html_path, tag_suggestions=vocab, experiment=args.experiment)
    print(f"[2] 勾选网页: {html_path}")

    # 3. 计划：优先外部 plan，否则全部选中、用占位总结/标签
    if args.plan:
        plan = utils.read_json(os.path.abspath(args.plan))
    else:
        selected = [{"name": r["name"], "date": r["date"], "album": r["album"]}
                    for r in records]
        plan = archive.plan_from_selection(selected, experiment=args.experiment)
    print(f"[3] 计划条数: {len(plan)}")

    # 4. dry-run 预览
    if args.dry_run:
        tree = archive.plan_tree(plan)
        print(f"[4] dry-run: 将生成 {len({t['folder'] for t in tree})} 个文件夹、{len(tree)} 张图")
        return 0

    # 5. 归档
    res = archive.archive(plan, source, out, copy=True, incremental=args.incremental,
                          figures_dir=figures_dir)
    print(f"[5] 归档: 文件夹 {res['folders']}, 照片 {res['photos']}, "
          f"缺失 {res['missing']}, 入论文 {res['figures']}, 跳过已存在 {res['skipped_existing']}")
    print(f"    清单: {res['manifest_path']}")
    print(f"    索引: {res['index_path']}")
    print(f"    对比报告: {res['report_path']}")
    print(f"    对照表: {res['mapping_path']}")
    print(f"    回滚清单: {res['rollback_path']}")

    # 5b. 跨实验台账追加
    manifest = utils.read_json(res["manifest_path"])
    ledger.add_batch(out, manifest, experiment=args.experiment or "未分组实验",
                     source_note=os.path.basename(source))
    print(f"    台账: {os.path.join(out, '归档台账.json')}")

    # 6. commit message 草稿
    draft = archive.commit_message_draft(manifest, experiment=args.experiment or "实验照片")
    print("[6] commit 草稿:\n    " + draft.replace("\n", "\n    "))
    return 0 if res["missing"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
