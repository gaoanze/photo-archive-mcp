# -*- coding: utf-8 -*-
"""单元测试：纯函数与确定性逻辑，不依赖手机/网络/私有路径。

运行：``python -m pytest tests/ -q``（未装 pytest 时也可用 ``python tests/test_core.py``）。
"""
import os
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from photo_archive_mcp import archive, config, fingerprint, ledger, scan, suggest, utils


def test_parse_date():
    assert utils.parse_date("IMG_20260915_103012.jpg") == "2026-09-15"
    assert utils.parse_date("image_1726350000.jpg") != "未知日期"
    assert utils.parse_date("random.png") == "未知日期"


def test_safe_name():
    assert utils.safe_name('a/b\\c*d:e?f"g<h>i|j') == "abcdefghij"
    assert utils.safe_name("  示例  记录 ") == "示例 记录"


def test_hamming():
    assert fingerprint.hamming(0, 0) == 0
    assert fingerprint.hamming(0b1111, 0b0000) == 4


def test_group_exact_duplicates():
    records = [
        {"name": "a.jpg", "sha1": "x", "phash": 1, "decoded": True},
        {"name": "b.jpg", "sha1": "x", "phash": 1, "decoded": True},
        {"name": "c.jpg", "sha1": "y", "phash": 2, "decoded": True},
    ]
    groups = fingerprint.group_duplicates(records, distance=6)
    assert len(groups["exact"]["x"]) == 2
    assert groups["exact"]["y"] == ["c.jpg"]


def test_plan_tree_naming_and_dedup():
    plan = [
        {"name": "a.jpg", "date": "2026-09-15", "summary": "示例记录", "tag": "现场实拍"},
        {"name": "b.jpg", "date": "2026-09-15", "summary": "示例记录", "tag": "现场实拍"},
    ]
    tree = archive.plan_tree(plan)
    assert tree[0]["folder"] == "2026-09-15-示例记录"
    assert tree[0]["new_name"].endswith("-01.jpg")
    assert tree[1]["new_name"].endswith("-02.jpg")
    names = {t["new_name"] for t in tree}
    assert len(names) == 2


def test_reverse_lookup(tmp_dir=None):
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix="pa_test_")
    src = os.path.join(tmp, "src")
    os.makedirs(src)
    for name in ("a.jpg", "b.jpg"):
        Image.new("RGB", (40, 30), (220, 220, 220)).save(os.path.join(src, name), "JPEG")
    out = os.path.join(tmp, "out")
    plan = [
        {"name": "a.jpg", "date": "2026-09-15", "summary": "记录", "tag": "现场实拍", "album": "Camera"},
        {"name": "b.jpg", "date": "2026-09-16", "summary": "记录", "tag": "谱图", "album": "Camera"},
    ]
    res = archive.archive(plan, src, out, copy=False)
    assert res["photos"] == 2
    assert len(archive.reverse_lookup(out, date="2026-09-15")) == 1
    assert len(archive.reverse_lookup(out, tag="谱图")) == 1
    assert len(archive.reverse_lookup(out, original="b.jpg")) == 1
    assert archive.reverse_lookup(out, keyword="不存在") == []


def test_commit_draft():
    manifest = [
        {"date": "2026-09-15", "file": "x-01.jpg"},
        {"date": "2026-09-15", "file": "x-02.jpg"},
        {"date": "2026-09-16", "file": "y-01.jpg"},
    ]
    draft = archive.commit_message_draft(manifest, experiment="demo-experiment")
    assert "归档 3 张" in draft
    assert "2026-09-15：2 张" in draft


def test_suggest_tag_rules():
    assert suggest.suggest_tag("Screenshot_20260915.jpg", "Screenshots") == "数据表格截图"
    assert suggest.suggest_tag("mmexport123.jpg", "微信") == "微信传输图"
    assert suggest.suggest_tag("random.png", "Camera") == "其他"


def test_vocab_merge():
    merged = suggest.merge_vocab(["现场实拍", "谱图"], ["谱图", "仪器读数"])
    assert merged == ["谱图", "仪器读数", "现场实拍"]


def test_experiment_grouping_and_mapping():
    plan = [
        {"name": "a.jpg", "date": "2026-09-15", "summary": "记录", "tag": "现场实拍",
         "experiment": "demo-experiment"},
    ]
    groups = suggest.group_experiments(plan)
    assert "demo-experiment" in groups
    mapping = ledger.target_mapping(
        [{"folder": "2026-09-15-记录", "file": "a-01.jpg", "original": "a.jpg",
          "date": "2026-09-15", "tag": "现场实拍"}],
        "/kb", experiment="demo-experiment")
    assert "demo-experiment" in mapping[0]["target"]


def test_ledger_add_and_query():
    tmp = tempfile.mkdtemp(prefix="pa_ledger_")
    manifest = [
        {"file": "a-01.jpg", "original": "a.jpg", "date": "2026-09-15", "tag": "现场实拍"},
        {"file": "b-01.jpg", "original": "b.jpg", "date": "2026-09-16", "tag": "谱图"},
    ]
    ledger.add_batch(tmp, manifest, experiment="exp-A", source_note="手机批次1")
    rows = ledger.query(tmp, experiment="exp-A")
    assert len(rows) == 2
    assert len(ledger.query(tmp, date="2026-09-15")) == 1
    summ = ledger.summary(tmp)
    assert summ["experiments"]["exp-A"]["photos"] == 2


def test_figures_export():
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix="pa_fig_")
    src = os.path.join(tmp, "src"); os.makedirs(src)
    Image.new("RGB", (40, 30), (220, 220, 220)).save(os.path.join(src, "a.jpg"), "JPEG")
    out = os.path.join(tmp, "out")
    plan = [{"name": "a.jpg", "date": "2026-09-15", "summary": "记录",
             "tag": "现场实拍", "flag": "paper"}]
    archive.archive(plan, src, out, copy=False)
    manifest = archive.reverse_lookup(out)
    res = archive.figures_export(manifest, os.path.join(tmp, "figures"))
    assert res["count"] == 1
    assert os.path.exists(res["csv_path"]) and os.path.exists(res["md_path"])


def test_config_deep_merge():
    cfg = config.load_config(None, overrides={"compress": {"quality": 70}})
    # 覆盖只改 quality，max_side 保留默认
    assert cfg["compress"]["quality"] == 70
    assert cfg["compress"]["max_side"] == 1600
    # 嵌套质量阈值保留默认
    assert cfg["quality"]["blur_threshold"] == 100.0
    assert cfg["cache"]["enabled"] is True


def test_scan_cache_reuse():
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix="pa_cache_")
    src = os.path.join(tmp, "src"); os.makedirs(src)
    Image.new("RGB", (60, 40), (200, 200, 200)).save(os.path.join(src, "a.jpg"), "JPEG")

    first = scan.scan_folder(src)
    assert len(first) == 1
    cache_file = os.path.join(src, ".scan_cache.json")
    assert os.path.exists(cache_file)

    # 未变更：二次扫描复用缓存，记录字段一致
    second = scan.scan_folder(src)
    assert len(second) == 1
    assert second[0]["sha1"] == first[0]["sha1"]
    assert second[0]["wh"] == first[0]["wh"]

    # 关闭缓存仍能扫描，且不写缓存依赖
    third = scan.scan_folder(src, use_cache=False)
    assert len(third) == 1


def test_summarize_orientation_and_bytes():
    records = [
        {"name": "land.jpg", "date": "2026-09-15", "album": "Camera", "size": 1000,
         "decoded": True, "wh": "60x40", "sha1": "a", "phash": 1},
        {"name": "port.jpg", "date": "2026-09-15", "album": "Camera", "size": 2000,
         "decoded": True, "wh": "40x60", "sha1": "b", "phash": 2},
        {"name": "sq.jpg", "date": "2026-09-16", "album": "WeChat", "size": 500,
         "decoded": True, "wh": "50x50", "sha1": "c", "phash": 3},
    ]
    summary = scan.summarize(records)
    assert summary["orientation"]["landscape"] == 1
    assert summary["orientation"]["portrait"] == 1
    assert summary["orientation"]["square"] == 1
    assert summary["by_album_bytes"]["Camera"] == 3000
    assert summary["by_album_bytes"]["WeChat"] == 500
    assert summary["total_bytes"] == 3500


def test_concurrent_scan_matches_serial():
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix="pa_conc_")
    src = os.path.join(tmp, "src"); os.makedirs(src)
    for i in range(6):
        Image.new("RGB", (50 + i, 40), (180, 180, 180)).save(
            os.path.join(src, f"IMG_20260915_{i:04d}.jpg"), "JPEG")

    serial = scan.scan_folder(src, cfg={"concurrency": {"workers": 1}}, use_cache=False)
    parallel = scan.scan_folder(src, cfg={"concurrency": {"workers": 4}}, use_cache=False)
    assert len(serial) == len(parallel) == 6
    # 记录按 (date, name) 排序，并发结果顺序与字段应与串行一致
    assert [r["name"] for r in serial] == [r["name"] for r in parallel]
    for a, b in zip(serial, parallel):
        assert a["sha1"] == b["sha1"]
        assert a["wh"] == b["wh"]
        assert a["decoded"] == b["decoded"]
        assert a["date"] == b["date"]


def test_concurrent_thumbs_preserve_order():
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix="pa_thumbs_")
    src = os.path.join(tmp, "src"); os.makedirs(src)
    thumbs = os.path.join(tmp, "thumbs")
    records = []
    for i in range(5):
        p = os.path.join(src, f"p{i}.jpg")
        Image.new("RGB", (60, 40), (170, 170, 170)).save(p, "JPEG")
        records.append({"name": f"p{i}.jpg", "rel": f"p{i}.jpg",
                        "source_full": p, "decoded": True})
    out = scan.build_thumbs(records, thumbs, workers=4)
    # 缩略图编号与记录顺序一一对应
    assert [r["thumb"] for r in out] == [f"t_{i:05d}.jpg" for i in range(1, 6)]
    assert all(os.path.exists(os.path.join(thumbs, r["thumb"])) for r in out)


def test_phone_source_dispatch():
    from photo_archive_mcp import phone_source
    # 分派函数在非 Windows 走本地目录后端；Windows 走 MTP 后端
    assert callable(phone_source.list_phones)
    assert callable(phone_source.clone)
    # 候选目录解析：仅返回真实存在的目录，展示名不含系统敏感路径
    cands = phone_source._posix_candidates()
    assert isinstance(cands, dict)
    for name, path in cands.items():
        assert os.path.isabs(path)
        assert os.sep not in name


def test_selection_page_script_order():
    """勾选网页的 JS 必须先声明 ``$`` 再使用，否则整页脚本会因 TDZ 报错白屏。"""
    from photo_archive_mcp import webpage
    rec = {"name": "IMG_20260915_103012.jpg", "date": "2026-09-15", "album": "Camera",
           "thumb": "t_00001.jpg", "size": 1024, "decoded": True}
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "selection.html")
        webpage.build_html([rec], out, title="demo", tag_suggestions=["现场实拍"], experiment="exp")
        text = open(out, encoding="utf-8").read()
    decl = text.find("const $ = id")
    first_use = text.find('$("expInput")')
    assert decl != -1 and first_use != -1
    assert decl < first_use, "`$` 在声明前被使用，页面会白屏"
    assert "__DATA__" not in text and "__TAGS__" not in text and "__EXP__" not in text


if __name__ == "__main__":
    test_parse_date()
    test_safe_name()
    test_hamming()
    test_group_exact_duplicates()
    test_plan_tree_naming_and_dedup()
    test_reverse_lookup()
    test_commit_draft()
    test_suggest_tag_rules()
    test_vocab_merge()
    test_experiment_grouping_and_mapping()
    test_ledger_add_and_query()
    test_figures_export()
    test_config_deep_merge()
    test_scan_cache_reuse()
    test_summarize_orientation_and_bytes()
    test_concurrent_scan_matches_serial()
    test_concurrent_thumbs_preserve_order()
    test_phone_source_dispatch()
    test_selection_page_script_order()
    print("unit tests OK")
