# photo-archive-mcp 完整使用手册

> README 之外的详细说明：每个步骤怎么用、数据格式长什么样、配置项、命名规则与边界。
> 快速上手看 [README](../README.md)。

## 全流程一览

```text
[手机]  ——MTP/WPD 或手动复制——▶  [本地克隆目录]
                                    │
                          1. scan_photos 扫描元数据 + 指纹 + 缩略图 + 去重/损坏清单
                                    │
                          2. build_selection_page 生成勾选网页
                                    │
                          3. 浏览器勾选 / 标记 → 导出「勾选照片清单.json」（可导入恢复）
                                    │
                          4. 读图理解（上层多模态/人工）：当日总结 + 逐张标签
                                    │
                          5. build_archive_plan 合并勾选清单与标签 → 归档计划
                                    │
                          6. preview_archive_plan dry-run 预览目录树（可选）
                                    │
                          7. archive_photos 分文件夹、重命名、复制、清单/索引/对比报告
                                    │
                          8. inspect_archive 核对数量/体积/清单索引齐全度
                                    │
                          9. lookup_archive 反向检索；draft_commit_message 拟入库信息
                                    │
                         10. 入库知识库（git 提交推送）/ 下载挪动到论文 figures/ 等目录
```

| 阶段 | 工具 / 动作 | 输入 | 产出 |
| --- | --- | --- | --- |
| ① 取图 | `list_phone_devices` | — | 已连接的便携设备列表 |
| ① 取图 | `clone_phone_photos` | 手机设备、本地目标目录 | 断点续传克隆到本地的图片 |
| ② 扫描 | `scan_photos` | 本地目录、缩略图目录、可选配置文件 | 图片记录 + 汇总（去重/损坏/指纹） |
| ③ 勾选 | `build_selection_page` | 扫描记录、HTML 输出路径 | 单文件勾选网页（数据内联、缩略图相对路径） |
| ③ 导出 | 网页「导出勾选清单 JSON」 | 勾选 / 标记 / 标签状态 | `勾选照片清单.json`（含全量状态，可再导入） |
| ④ 理解 | 上层多模态 / 人工 | 照片、实验报告记录 | `summaries={日期: 总结}`、`tags={文件名: 标签}` |
| ⑤ 计划 | `build_archive_plan` | 勾选清单、总结、标签 | 归档计划 `plan` |
| ⑥ 预览 | `preview_archive_plan` | 计划 | dry-run 目录树（不碰磁盘） |
| ⑦ 归档 | `archive_photos` | 计划、源目录、输出目录、增量/figures 选项 | 归档图片 + 清单 + 索引 + 对比报告 |
| ⑧ 核对 | `inspect_archive` | 归档输出目录 | 文件夹数、图片数、总体积、清单/索引是否齐全 |
| ⑨ 检索 | `lookup_archive` | 归档目录、关键词/日期/标签/原始名 | 命中的追溯条目 |
| ⑨ 草稿 | `draft_commit_message` | 归档目录、实验名 | 入库 commit message 草稿 |
| ⑩ 选片 | `suggest_tags` | 扫描记录、历史归档目录? | 逐张建议标签 + 合并历史词表 |
| ⑩ 治理 | `export_compressed` | 归档目录、压缩目录、边长/质量? | 压缩副本（原图保留）+ 体积对比 |
| ⑩ 治理 | `quality_filter` | 归档目录、模糊阈值? | 模糊/过暗/过亮候选清单与指标 |
| ⑩ 治理 | `export_figures` | 归档目录、配图清单目录 | 论文配图 CSV + Markdown（自动编图号） |
| ⑩ 衔接 | `update_ledger` | 台账目录、实验名、来源说明? | 追加跨实验台账批次 |
| ⑩ 衔接 | `query_ledger` | 台账目录、实验名?、日期? | 台账文件级检索与汇总 |
| ⑩ 衔接 | `target_mapping` | 归档目录、知识库根目录、实验名? | 归档文件 → 知识库目标路径映射表 |
| ⑪ 入库 | 外部 git 流程（见下文） | 归档目录 | 提交并推送到知识库仓库 |

## 工具清单

| 工具名 | 阶段 | 参数 | 说明 |
| --- | --- | --- | --- |
| `list_phone_devices` | 取图 | — | 列出可导入来源：Windows 为 MTP 便携设备；macOS/Linux 为本地照片目录 |
| `clone_phone_photos` | 取图 | `dest_dir`、`phone_name?` | 把图片断点续传克隆到本地；Windows 走 MTP，macOS/Linux 复制本地目录；已存在同名文件跳过 |
| `scan_photos` | 扫描 | `source_dir`、`thumbs_dir?`、`max_side?`、`config_path?` | 递归扫描，提取日期/相册/尺寸/指纹/能否解码，给出重复与损坏清单，可生成缩略图 |
| `build_selection_page` | 勾选 | `records`、`html_path`、`title?` | 生成单文件勾选网页；缩略图需放在同目录 `thumbs/` 下 |
| `build_archive_plan` | 计划 | `selected`、`summaries?`、`tags?` | 把勾选清单与当日总结、逐张标签合并成归档计划 |
| `preview_archive_plan` | 预览 | `plan` | dry-run 列出将要生成的文件夹与文件名，不触碰磁盘 |
| `archive_photos` | 归档 | `plan`、`source_dir`、`out_dir`、`copy?`、`source_dirs?`、`incremental?`、`figures_dir?` | 按日期建文件夹、重命名、复制，生成清单/索引/对比报告；支持多源目录、增量归档、论文图另存 |
| `inspect_archive` | 核对 | `out_dir` | 统计文件夹数、图片数、总体积，确认清单与索引齐全 |
| `lookup_archive` | 检索 | `out_dir`、`keyword?`、`date?`、`tag?`、`original?` | 按归档名/原始名/日期/标签反向追溯 |
| `draft_commit_message` | 入库 | `out_dir`、`experiment?` | 根据归档清单生成入库 commit message 草稿 |
| `suggest_tags` | 选片 | `records`、`history_dir?` | 按文件名/相册规则给建议标签，可合并历史归档用过的标签词表 |
| `export_compressed` | 治理 | `out_dir`、`compress_dir`、`max_side?`、`quality?` | 另存压缩副本（沿用目录结构，原图保留），返回压缩前后体积对比 |
| `quality_filter` | 治理 | `out_dir`、`blur_threshold?` | 纯 Pillow 计算清晰度/亮度/比例，筛出模糊、过暗、过亮候选 |
| `export_figures` | 衔接 | `out_dir`、`figures_dir` | 导出标记 `paper` 的配图清单（CSV + Markdown，自动编 `Fig.01` 图号） |
| `update_ledger` | 衔接 | `ledger_dir`、`experiment?`、`source_note?`、`committed?` | 把归档清单追加进跨实验台账 |
| `query_ledger` | 衔接 | `ledger_dir`、`experiment?`、`date?` | 按实验/日期检索台账条目并返回汇总 |
| `target_mapping` | 衔接 | `out_dir`、`knowledge_root`、`experiment?` | 生成归档文件到知识库目标目录的映射表（只出表，不复制） |

## 各步骤详解

### ① 把手机照片传到电脑

**方式 A：直连克隆（按平台分派）**

- **Windows**：手机通过数据线连接电脑并解锁，系统识别为便携设备（MTP/WPD）后，
  走 pywin32 的 Shell.Application 读取；
- **macOS / Linux**：无便携设备命名空间接口，自动扫描 `~/Pictures`、`~/DCIM`、
  `~/Photos`、`~/Downloads` 等常见照片目录，把存在的目录作为可导入来源，克隆时复制文件。

1. `list_phone_devices()` 查看设备 / 来源名。
2. `clone_phone_photos(dest_dir="./phone_import", phone_name=...)` 克隆图片。
   - 带断点续传：再次运行时已存在的同名文件自动跳过，只补传缺失项。
   - 克隆结果里会写一份 `_phone_meta.json`，记录原始路径、日期、相册。

**方式 B：手动复制（任意系统）**

没有可用后端（如 Windows 未装 pywin32、macOS/Linux 未找到照片目录）时，直接用系统
文件管理器把手机相册图片复制到本地目录，再从第 ② 步开始。

### ② 扫描本地目录

`scan_photos(source_dir="./phone_import", thumbs_dir="./thumbs", config_path="./config.json")`
递归扫描所有图片，跳过系统变换缓存目录（`.transforms`、`.thumbnails`、`.gs`、`.trashed` 等），返回：

- 每条记录：`name` / `date` / `date_source` / `album` / `rel` / `size` / `wh` /
  `decoded` / `sha1` / `phash` / `cluster` / `thumb`；
- 汇总：总数、可解码数、未解码数、按日期/相册分组、总体积、按相册体积、横/竖/方比例分布、
  损坏清单、重复分组。

### ③ 生成勾选网页并导出清单

`build_selection_page(records, html_path="./挑选台.html")` 生成可直接用浏览器打开的单文件网页，
详见 [勾选网页能力](#勾选网页能力)。

### ④ 读图理解（上层完成）

对照实验报告 / 原始记录，逐张判断图片内容，产出两份映射：

- `summaries = {"2026-09-15": "示例实验记录"}` —— 当日一句话总结；
- `tags = {"IMG_20260915_103012.jpg": "现场实拍"}` —— 逐张内容标签。

这一步不在本服务内执行；可由多模态 Agent 读图生成，或人工填写。

### ⑤ 合并归档计划

`build_archive_plan(selected, summaries, tags)` 把勾选清单与总结、标签合并成计划条目，
每条含 `name` / `date` / `album` / `rel` / `summary` / `tag` / `flag`；
缺省总结用「实验记录」，缺省标签用「照片」。

### ⑥ dry-run 预览

`preview_archive_plan(plan)` 只列出将要生成的文件夹与文件名，不复制、不写清单，
便于落地前核对命名与分组；确认无误后再执行归档。

### ⑦ 分文件夹归档与重命名

`archive_photos(plan, source_dir="./phone_import", out_dir="./archive_ready", figures_dir="./figures")`：

- 按日期建文件夹，文件名按命名规则重命名并复制到输出目录；同名自动避让编号；
- 生成追溯清单 `归档清单.json`（新文件名 ↔ 原始文件名 ↔ 来源相册 ↔ 日期 ↔ 标签 ↔ 标记）；
- 生成 Markdown 索引 `照片索引.md`，按文件夹列出条目表；
- 生成 `归档对比报告.json`：计划数 / 归档数 / 缺失 / 跳过已存在 / 冲突 / 入论文数量，按日期对照；
- `copy=False` 时只生成清单与索引，不移动/复制源文件。

### ⑧ 核对归档结果

`inspect_archive(out_dir="./archive_ready")` 返回文件夹数、图片数、总体积，
以及清单、索引是否存在；`missing` 为计划里找不到源文件的条目，需回头补传或修正。

### ⑨ 反向检索与入库草稿

- `lookup_archive(out_dir, keyword=..., date=..., tag=..., original=...)`：在归档清单里
  按归档文件名关键词、原始文件名、日期或标签反查追溯条目；
- `draft_commit_message(out_dir, experiment="demo-experiment")`：按归档清单生成入库 commit message 草稿，
  首行汇总总数，后续按日期批次列出数量。

## 数据质量与去重

扫描阶段自动完成以下质量检查，结果写入汇总：

- **精确重复**：按文件字节 SHA-1 分组，同一张图被转发多次会归到同一组；
- **疑似相似**：按感知哈希（pHash）汉明距离分组，容忍缩放与轻微压缩；阈值可在配置里调整；
- **损坏 / 无法解码清单**：打不开的图片标记 `decoded=false`，单独列入 `broken`，便于回头重传；
- **日期兜底**：先从文件名解析日期；解析不到再读 EXIF 拍摄时间；仍取不到记为「未知日期」，
  并在 `date_source` 字段标明日期来源（`filename` / `exif`）；
- **格式归一**：HEIC/HEIF 在归档时可配置转为 JPG（`convert_heic`）；当前环境缺少 HEIF 插件时
  降级为保留原片并标记不可解码，不报错中断。

## 勾选网页能力

单文件网页（数据内联、缩略图相对 `thumbs/` 路径，可 `file://` 直接打开）支持：

- **大图预览**：点缩略图放大查看，便于判断内容后再勾选；
- **勾选状态导入 / 导出**：导出 JSON 同时保存勾选、标记与逐张标签；下次打开可导入恢复；
- **两类收藏标记**：「论文」（入论文正文）与「留档」（仅留档），归档时 `flag=paper` 的图
  可另存到 `figures/`；
- **框选多选**：在空白处按住拖动，框内卡片批量勾选；
- **多维筛选**：按日期、相册、状态（已勾选/未勾选/论文/留档）、可解码/损坏、文件大小筛选，
  按文件名或标签搜索；
- **相似聚类**：可切换按相似簇分组展示；
- **逐张标签**：卡片内可直接编辑标签，随清单一起导出。

## 归档追溯与入库衔接

- **冲突检测与命名防重**：同目录同名文件自动追加避让编号；归档结果里记录 `conflicts`；
- **归档前后对比报告**：`归档对比报告.json` 对照计划与实际归档数量，列出缺失、冲突、入论文清单；
- **反向检索**：归档文件名 ↔ 原始文件名 / 来源相册 / 日期 / 标签，见 `lookup_archive`；
- **增量归档**：`incremental=True` 时跳过已在归档清单中的原始文件名，第二次跑只处理新增照片；
- **多源目录**：`source_dirs` 传入多个候选目录，按顺序定位源文件；
- **dry-run 目录树预览**：`preview_archive_plan` 落地前查看将要生成的结构；
- **论文 figures 导出**：`figures_dir` 指定后，标记 `paper` 的图另存并写 `figures_清单.json`；
- **commit message 草稿**：`draft_commit_message` 生成可直接用于知识库提交的信息草稿。

## 选片提效

- **标签建议（纯规则，不做图像理解）**：`suggest_tags` 按文件名/相册关键词匹配规则给出候选标签，
  建议值对齐配置词表；规则未命中归到「其他」。
- **历史词表记忆**：传入 `history_dir`（已有归档目录）时，读取历史 `归档清单.json` 里用过的标签
  与当日总结，合并进候选词表，跨批次沿用同一套术语。
- **实验分组**：计划条目可带 `experiment` 字段；归档时输出目录下再分一层
  `experiments/<实验>/<日期文件夹>/`，清单与索引条目均带实验名，便于一个知识库内并存多组实验。

## 图片治理

- **方向校正**：读取图片时按 EXIF 方向信息自动转正（`ImageOps.exif_transpose`），缩略图、压缩副本、
  质量指标都基于校正后的画面。
- **压缩副本**：`export_compressed` 为归档图片另存 JPG 副本（默认最长边 1600px、质量 82），沿用归档
  目录结构；原始大图保留在归档目录不动，返回压缩前后体积与压缩比。
- **质量筛查**：`quality_filter` 用纯 Pillow 计算灰度方差（清晰度分）、平均亮度与横/竖/方比例，
  把模糊（低于阈值）、过暗、过亮的候选单独标出；阈值见配置。
- **对照回滚**：归档同时写出 `归档对照表.json`（原始名 ↔ 归档名 ↔ 目录 ↔ 日期/标签）与
  `回滚清单.json`（归档路径 ↔ 原始名 ↔ 日期）；回滚按清单删除已复制的归档文件，源克隆目录不受影响。

## 入库衔接

- **跨实验台账**：`update_ledger` 把一次归档清单追加到 `归档台账.json`，按实验聚合批次（张数、体积、
  日期覆盖、是否已入库）；`query_ledger` 按实验/日期做文件级检索，`summary` 返回各实验汇总。
- **入库目录映射**：`target_mapping` 只出映射表不执行复制，目标结构为
  `<knowledge_root>/experiments/<experiment>/<日期文件夹>/<文件名>`，核对后再由外部流程挪动/提交。
- **论文配图清单**：`export_figures` 只取标记 `paper` 的图，按日期+标签排序自动编 `Fig.01` 图号，
  同时写 CSV（UTF-8 BOM，Excel 可直接打开）与 Markdown 表格。

## 数据格式

### 勾选照片清单（网页导出）

```json
{
  "total": 3,
  "groups": [
    {
      "date": "2026-09-15",
      "photos": [
        { "name": "IMG_20260915_103012.jpg", "album": "Camera", "thumb": "t_00001.jpg",
          "tag": "现场实拍", "flag": "paper" }
      ]
    }
  ],
  "state": { "IMG_20260915_103012.jpg": { "checked": true, "flag": "paper", "tag": "现场实拍" } }
}
```

### 归档计划（`build_archive_plan` 产出 / `--plan` 输入）

```json
[
  {
    "name": "IMG_20260915_103012.jpg",
    "date": "2026-09-15",
    "album": "Camera",
    "summary": "示例实验记录",
    "tag": "现场实拍",
    "flag": "paper",
    "experiment": "demo-experiment"
  }
]
```

`flag` 取值：`paper`（入论文）、`archive`（仅留档）、空字符串（不标记）；`experiment` 为可选实验名，归档时作为子目录分组。

### 追溯清单（`归档清单.json`）

每条记录归档后的新文件名、原始文件名、来源相册、日期、标签与标记，便于追溯与核对。

### 对比报告（`归档对比报告.json`）

```json
{
  "plan_total": 7,
  "archived_total": 7,
  "missing_total": 0,
  "skipped_existing_total": 0,
  "conflict_total": 0,
  "figures_total": 2,
  "by_date_plan": { "2026-09-15": 3 },
  "by_date_archived": { "2026-09-15": 3 },
  "missing_names": [],
  "conflicts": [],
  "figures": []
}
```

### 对照表 / 回滚清单

- `归档对照表.json`：每条 `original`（原始名）↔ `file`（归档名）↔ `folder` ↔ `date` / `tag` / `album`。
- `回滚清单.json`：每条 `archive_path`（相对归档目录）、`original`、`date`，用于按清单删除已复制的归档文件。

### 配图清单（`export_figures` 产出）

标记 `paper` 的图按日期+标签排序，自动编 `Fig.01` 图号，写出两份：

- `论文配图清单.csv`：图号、日期、实验、标签、归档文件、原始文件名、目录（UTF-8 BOM，Excel 可读）；
- `论文配图清单.md`：同样内容的 Markdown 表格。

### 跨实验台账（`归档台账.json`）

按实验名聚合批次，每条批次记录归档时间、来源说明、张数、总体积、按日期分布、是否已入库，以及文件级明细。

### 入库映射表（`target_mapping` 产出）

每条 `source`（归档相对路径）↔ `target`（知识库目标绝对路径）↔ `original` / `date` / `tag`；只出表，不执行复制。

## 命名规则

- 文件夹：`YYYY-MM-DD-当日一句话总结`
  例：`2026-09-15-示例实验记录`
- 图片：`文件夹名-内容标签-编号.扩展名`
  例：`2026-09-15-示例实验记录-现场实拍-03.jpg`
- 文件名中的非法字符（`\ / : * ? " < > |` 等）会被自动净化，空白与多余连字符压缩。

## 配置文件

可选 JSON 配置（示例见 `examples/config.example.json`），通过 `scan_photos` 的 `config_path` 传入：

| 键 | 说明 | 默认 |
| --- | --- | --- |
| `image_exts` | 参与归档的图片扩展名 | jpg/jpeg/png/heic/heif/webp/gif/bmp |
| `skip_dir_marks` | 递归扫描时跳过的目录名标记 | 系统缓存/占位目录 |
| `thumb_max_side` | 缩略图最长边像素 | 320 |
| `thumb_quality` | 缩略图 JPG 质量 | 78 |
| `phash_size` | 感知哈希缩略尺寸 | 8 |
| `phash_distance` | 相似判定汉明距离阈值 | 6 |
| `convert_heic` | HEIC 是否转 JPG | true |
| `tag_suggestions` | 网页标签建议词表 | 内置常见实验标签 |
| `quality.blur_threshold` | 清晰度（灰度方差）低于该值判为模糊 | 100.0 |
| `quality.brightness_min/max` | 平均亮度越界判为过暗/过亮 | 30 / 235 |
| `compress.max_side` | 压缩副本最长边像素 | 1600 |
| `compress.quality` | 压缩副本 JPG 质量 | 82 |
| `cache.enabled` | 是否启用扫描缓存（未变文件复用上次指纹/日期/尺寸） | true |
| `concurrency.workers` | 指纹解码与缩略图生成的工作线程数；1 为串行 | 4 |

## 目录结构

```text
photo-archive-mcp/
├── photo_archive_mcp/
│   ├── __init__.py
│   ├── server.py        # MCP 工具注册（stdio，17 个工具）
│   ├── config.py        # 默认配置与配置文件读取
│   ├── fingerprint.py   # SHA-1 / pHash / EXIF 日期 / 去重分组 / HEIC 转换 / 方向校正 / 质量指标
│   ├── scan.py          # 扫描元数据 + 指纹 + 缩略图 + 汇总 + 进度回调
│   ├── webpage.py       # 单文件勾选网页生成器（建议标签 / 实验名 / 下拉选择）
│   ├── archive.py       # 计划合并 / 重命名 / 索引 / 报告 / 检索 / 草稿 / 压缩 / 质量筛查 / 配图清单
│   ├── suggest.py       # 标签建议规则 / 历史词表记忆 / 实验分组
│   ├── ledger.py        # 跨实验台账：追加 / 检索 / 汇总 / 入库目录映射
│   ├── phone_source.py  # 取图后端分派：Windows MTP/WPD（pywin32）/ macOS·Linux 本地照片目录
│   └── utils.py         # 文件名净化、日期解析、JSON 读写
├── tests/
│   └── test_core.py     # 纯函数与确定性逻辑单元测试
├── examples/
│   ├── archive_plan.example.json  # 归档计划示例
│   ├── config.example.json        # 配置文件示例
│   ├── selftest.py      # 合成样例端到端自测（不依赖手机/网络/私有路径）
│   └── cli_demo.py      # 命令行演示：扫描 → 网页 → 预览/归档/检索/台账
├── .github/workflows/
│   └── test.yml         # CI：多版本 Python 跑单元测试与端到端自测
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 安装

```bash
# 建议虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -e .
# 需要从手机直连克隆时（仅 Windows，可选）：
pip install -e ".[phone]"
```

依赖：`mcp>=2.0.0`、`Pillow>=10.0.0`；手机直连额外需要 `pywin32`（仅 Windows）。

## 在 MCP 客户端中接入

stdio 方式，把下面配置加入你的 MCP 客户端配置（路径换成实际安装位置）：

```json
{
  "mcpServers": {
    "photo-archive": {
      "command": "python",
      "args": ["-m", "photo_archive_mcp.server"],
      "cwd": "/absolute/path/to/photo-archive-mcp"
    }
  }
}
```

启动后客户端会自动发现上面 17 个工具；按 [全流程一览](#全流程一览) 的顺序调用即可。

## 自测与测试

```bash
# 端到端自测：临时目录现造合成样例图，跑通扫描→网页→计划→归档→检索→增量→
# 标签建议→压缩副本→质量筛查→配图清单→台账→入库映射
python examples/selftest.py

# 单元测试：日期解析 / 命名净化 / 哈希 / 去重分组 / 计划树 / 检索 / 草稿 /
# 标签规则 / 词表合并 / 实验分组 / 台账 / 配图清单
python tests/test_core.py
# 或：python -m pytest tests/ -q

# 命令行演示：指定自己的图片目录，直接生成勾选网页与归档结果
python examples/cli_demo.py --source ./photos --out ./archive_ready

# dry-run 预览、增量归档、论文图另存：
python examples/cli_demo.py --source ./photos --out ./archive_ready \
    --dry-run --incremental --figures ./figures

# 按关键词反查已有归档：
python examples/cli_demo.py --source ./photos --out ./archive_ready --lookup 谱图
```

`cli_demo.py` 参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--source` | 是 | 待归档图片所在目录 |
| `--out` | 是 | 归档输出目录 |
| `--plan` | 否 | 归档计划 JSON 路径；不传则全部选中、用占位总结/标签 |
| `--html` | 否 | 勾选网页输出路径，默认 `<out>/挑选台.html` |
| `--thumbs` | 否 | 缩略图目录，默认 `<out>/thumbs` |
| `--figures` | 否 | 入论文图片另存目录 |
| `--experiment` | 否 | 实验名，归档时作为子目录分组并写入台账 |
| `--dry-run` | 否 | 只生成计划目录树预览，不复制文件 |
| `--incremental` | 否 | 跳过已归档的原始文件名 |
| `--lookup` | 否 | 按关键词反向检索已有归档清单 |

## 入库与挪动约定

归档产物核对通过后，进入知识库的方式由外部流程完成，本工具不直接写远程仓库：

- **入知识库**：把 `archive_ready/` 下按日期分好的文件夹复制/移动到知识库对应实验目录，
  再用 git 提交并推送；`归档清单.json`、`照片索引.md`、`归档对比报告.json` 随目录一并入库，方便后续检索复盘。
- **下载 / 二次挪动**：需要进论文正文的图，从归档目录另存到论文目录的 `figures/`；
  原始大图留在素材归档目录，避免反复压缩损耗。
- **原始数据不覆盖**：归档默认是复制（`copy=True`），源克隆目录保留；
  确认入库无误后再清理本地临时克隆（`phone_import/`、`thumbs/` 等已在 `.gitignore` 排除，不进库）。

## 边界说明

- **读图理解不在本服务内硬编码**：判断图片内容、归纳当日总结与标签属于多模态判断，
  由上层 Agent 或人工完成，结论写进计划的 `summary` / `tag` 字段，归档模块只做确定性落地。
- **取图按平台分派**：Windows 通过 pywin32 的 Shell.Application 直连 MTP/WPD 便携设备；
  macOS / Linux 扫描常见本地照片目录（`~/Pictures`、`~/DCIM`、`~/Photos`、`~/Downloads`），
  克隆时复制文件。两端都支持断点续传；无可用后端时提示先手动复制到本地目录。
- **HEIC 解码依赖插件**：缺少 HEIF 插件时 HEIC 标记为不可解码，不中断流程；安装对应插件后可自动转 JPG。
- **本工具不操作远程仓库**：取图、整理、归档在本地完成；提交推送知识库属于外部 git 流程。
- **扫描缓存**：未变更文件（相对路径 + mtime + 大小一致）复用上一次的指纹、日期与尺寸，
  不重复解码与哈希；缓存落在源目录 `.scan_cache.json`，可用配置 `cache.enabled` 关闭。
- **质量阈值与压缩参数已配置化**：模糊/亮度阈值见 `quality.*`，压缩边长/质量见 `compress.*`；
  工具调用时未显式传参即取配置默认值。
- **并发处理**：指纹解码与缩略图生成用线程池并发，工作线程数见 `concurrency.workers`
  （默认 4，设为 1 即串行）；记录顺序与缩略图编号保持稳定，缓存结构不变。

## License

MIT
