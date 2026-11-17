# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本。

## [Unreleased]

### Added

- 自制 README 徽章（MCP 17 tools / 100% local / platforms / research photos / MIT），SVG 放在 `assets/badges/`。
- 项目 Logo（`assets/logo.svg`、`assets/logo-512.png`）与 1280×630 社交预览图（`assets/social-preview.png`，含 HTML 模板）。

## [0.2.0] - 2026-11-17

### Added

- 开源发布：MIT License、中英文 README、完整使用手册（`docs/USAGE.zh-CN.md`）、贡献与安全说明。
- 勾选网页（`build_selection_page`）示例截图，作为 README 演示。
- 回归测试 `test_selection_page_script_order`，防止页面脚本初始化顺序回退。
- 许可与第三方声明：依赖许可证（mcp / Pillow / pywin32）、素材来源与商标说明。
- 示例数据统一改为中性占位内容，演示截图改用脚本合成的示意图。

### Fixed

- 修复勾选网页白屏：`$` DOM 助手在使用之后才声明，导致脚本 TDZ 报错、页面不渲染卡片。

### Changed

- README 重构为「快速上手 + 工具总览」，细节移入 `docs/USAGE.zh-CN.md`。

## [0.1.0] - 2026-11-17

### Added

- 初版：扫描 / 勾选网页 / 归档计划 / 重命名归档 / 索引与核对。
- 去重与损坏清单、EXIF 兜底、网页预览导入导出、归档报告与检索、增量归档与配图清单。
- 标签建议与词表记忆、压缩副本、方向校正、质量筛查、对照回滚、跨实验台账、入库映射。
- 指纹与缩略图线程池并发，macOS/Linux 本地照片目录取图后端。
- CI（Python 3.10 / 3.12）与端到端自测脚本。
