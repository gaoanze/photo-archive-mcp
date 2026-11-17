# -*- coding: utf-8 -*-
"""端到端自测：生成合成样例图片 → 扫描 → 网页 → 计划 → 归档 → 核对 → 检索。

不依赖手机、网络或任何本机私有路径；样例图片在临时目录里用 Pillow 现造。
运行：``python examples/selftest.py``
"""
import json
import os
import re
import shutil
import sys
import tempfile

from PIL import Image, ImageDraw

# 以脚本位置定位项目根，避免硬编码绝对路径
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from photo_archive_mcp import archive, fingerprint, ledger, scan, suggest, utils, webpage

# 1. 在临时目录造 7 张合成图，覆盖两个日期；其中两张内容完全相同（精确重复）
tmp = tempfile.mkdtemp(prefix="pa_mcp_test_")
src = os.path.join(tmp, "photos")
os.makedirs(src)

samples = [
    ("IMG_20260915_103012.jpg", "2026-09-15", "Camera", "示例实验记录", "现场实拍", (200, 120), ""),
    ("IMG_20260915_103548.jpg", "2026-09-15", "Camera", "示例实验记录", "实验操作记录", (210, 130), "paper"),
    ("Screenshot_20260915_110233.jpg", "2026-09-15", "Screenshots", "示例实验记录", "数据表格截图", (180, 140), ""),
    ("IMG_20260916_091205.jpg", "2026-09-16", "Camera", "实验方案与数据记录", "现场实拍", (190, 125), ""),
    ("IMG_20260916_091840.jpg", "2026-09-16", "Camera", "实验方案与数据记录", "检测记录图", (200, 135), "paper"),
    ("IMG_20260916_092511.jpg", "2026-09-16", "Camera", "实验方案与数据记录", "微信传输图", (170, 115), "archive"),
    ("IMG_20260916_093020.jpg", "2026-09-16", "Camera", "实验方案与数据记录", "现场实拍", (190, 125), ""),
]

for name, _date, _album, _summary, _tag, size, _flag in samples:
    im = Image.new("RGB", size, (230, 235, 240))
    ImageDraw.Draw(im).rectangle([10, 10, size[0] - 10, size[1] - 10], outline=(90, 120, 160))
    im.save(os.path.join(src, name), "JPEG", quality=80)
# 复制一张完全相同的图，制造精确重复
shutil.copy2(os.path.join(src, samples[0][0]), os.path.join(src, "COPY_" + samples[0][0]))

# 2. 扫描（含指纹/重复分组/损坏清单）
records = scan.scan_folder(src)
for r in records:
    r["source_full"] = os.path.join(src, r["rel"])
records = scan.build_thumbs(records, os.path.join(tmp, "thumbs"))
summary = scan.summarize(records)
print(f"[1] 扫描: {summary['total']} 张, 可解码 {summary['decoded']}, "
      f"日期组 {len(summary['by_date'])}, 精确重复 {summary['duplicates']['exact_count']}, "
      f"相似 {summary['duplicates']['similar_count']}, 损坏 {len(summary['broken'])}")

# 3. 生成勾选网页
html = os.path.join(tmp, "挑选台.html")
webpage.build_html(records, html)
print(f"[2] 网页生成: {os.path.exists(html)} ({os.path.getsize(html)} 字节)")

# 4. dry-run 预览（不落盘）
selected = [{"name": n, "date": d, "album": a, "flag": f}
            for n, d, a, _s, _t, _sz, f in samples]
summaries, tags = {}, {}
for _n, d, _a, s, t, _sz, _f in samples:
    summaries.setdefault(d, s)
    tags[_n] = t
plan = archive.plan_from_selection(selected, summaries=summaries, tags=tags)
preview = archive.plan_tree(plan)
print(f"[3] dry-run 预览: {len(preview)} 条, 文件夹 {len({t['folder'] for t in preview})}")

# 5. 落地归档，figures 目录接收入论文标记的图
out = os.path.join(tmp, "archive_ready")
fig_dir = os.path.join(tmp, "figures")
res = archive.archive(plan, src, out, figures_dir=fig_dir)
print(f"[4] 归档: 文件夹 {res['folders']}, 照片 {res['photos']}, 缺失 {res['missing']}, "
      f"入论文 {res['figures']}")

# 6. 核对清单、命名规则、对比报告
manifest = utils.read_json(res["manifest_path"])
bad = [m["file"] for m in manifest
       if not re.match(r"^\d{4}-\d{2}-\d{2}-.+-.+-\d{2}\.", m["file"])]
report = utils.read_json(res["report_path"])
print(f"[5] 清单 {len(manifest)} 条, 命名不合规 {len(bad)}, 报告计划 {report['plan_total']} / "
      f"归档 {report['archived_total']}, 索引存在 {os.path.exists(res['index_path'])}")

# 7. 反向检索：按日期与标签
by_date = archive.reverse_lookup(out, date="2026-09-16")
by_tag = archive.reverse_lookup(out, tag="现场实拍")
figs = archive.reverse_lookup(out)
paper = [m for m in figs if m["flag"] == "paper"]
print(f"[6] 检索: 09-16 共 {len(by_date)} 张, 标签「现场实拍」{len(by_tag)} 张, 入论文 {len(paper)} 张")

# 8. commit message 草稿
draft = archive.commit_message_draft(manifest)
print(f"[7] commit 草稿首行: {draft.splitlines()[0]}")

# 9. 增量归档：再次跑同一计划，已归档原始名应被跳过
res2 = archive.archive(plan, src, out, incremental=True)
print(f"[8] 增量复跑: 跳过已存在 {res2['skipped_existing']}, 本次归档 {res2['photos']}")

# 9. 标签建议 + 历史词表 + 实验分组
suggestions = suggest.suggest_tags_for_records(records)
history = suggest.load_history_vocab(out)
plan_exp = archive.plan_from_selection(selected, summaries=summaries, tags=tags,
                                      experiment="demo-experiment")
groups = suggest.group_experiments(plan_exp)
print(f"[9] 标签建议 {len(suggestions)} 条, 历史标签 {len(history['tags'])}, "
      f"实验分组 {len(groups)} 组")

# 10. 压缩副本 + 质量筛查 + 配图清单
comp = archive.export_compressed(manifest, out, os.path.join(tmp, "compressed"))
qrows = archive.quality_filter(manifest, out)
fig = archive.figures_export(manifest, os.path.join(tmp, "figures_list"))
print(f"[10] 压缩副本 {comp['files']} 张(压缩比 {comp['ratio']}), 质量筛查 {len(qrows)} 张, "
      f"配图清单 {fig['count']} 张")

# 11. 台账追加 / 检索 / 汇总 + 入库目录映射
ledger.add_batch(out, manifest, experiment="demo-experiment", source_note="自测批次")
ledger_rows = ledger.query(out, experiment="demo-experiment")
mapping = ledger.target_mapping(manifest, "/kb", experiment="demo-experiment")
print(f"[11] 台账条目 {len(ledger_rows)}, 入库映射 {len(mapping)} 条")

shutil.rmtree(tmp)
ok = (res["photos"] == len(plan) and not bad and res["missing"] == 0
      and res["figures"] == 2 and len(by_date) >= 3 and len(paper) == 2
      and summary["duplicates"]["exact_count"] >= 1 and res2["photos"] == 0
      and comp["files"] >= 1 and fig["count"] == 2 and len(ledger_rows) == len(manifest))
print("自测通过" if ok else "自测存在问题")
sys.exit(0 if ok else 1)
