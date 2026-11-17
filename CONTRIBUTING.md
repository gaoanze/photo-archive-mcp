# 参与贡献 / Contributing

谢谢你有兴趣改进 `photo-archive-mcp`。这个项目保持小而专注：**只做确定性的本地文件整理**，不引入网络请求、不上传数据、不内置视觉模型。

## 开发环境

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e .                # Windows 手机直连：pip install -e ".[phone]"
```

依赖刻意保持精简（`mcp` + `Pillow`，Windows 取图可选 `pywin32`）。新增依赖前请先开 issue 讨论。

## 提交前自测

```bash
python tests/test_core.py
python examples/selftest.py
```

CI 会在 Python 3.10 / 3.12 上跑同样的命令；本地通过后再提 PR。

## 报告问题

- 用 [Bug 模板](https://github.com/gaoanze/photo-archive-mcp/issues/new?template=bug_report.yml) 提 issue，附上操作系统、Python 版本、复现步骤和报错信息。
- **不要**在 issue 里贴真实实验照片、手机相册路径或个人目录结构；用合成图或占位路径复现。
- 安全问题请走 [SECURITY.md](SECURITY.md)。

## 提交 PR

1. 一个 PR 只做一件事，先开 issue 对齐需求。
2. 新功能补单元测试（`tests/test_core.py`），涉及页面改动的补一条断言。
3. 保持向后兼容：已有 JSON 字段和工具参数不要随意改名。
4. 更新 `CHANGELOG.md` 的 `Unreleased` 段落。
5. 描述里写清楚：改了什么、为什么、怎么验证的。

## 代码风格

- 只依赖标准库 + Pillow；文件操作做好异常兜底（坏图、权限、编码）。
- 所有路径参数用绝对路径或显式相对路径，不写死本机路径。
- 输出保持纯文本 JSON/Markdown，方便 diff。
- 注释解释"为什么"，不解释"是什么"。
