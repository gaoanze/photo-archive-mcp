# 安全说明 / Security

## 设计边界

`photo-archive-mcp` 是一个**纯本地**工具：不发起网络请求、不上传文件、不写入远程仓库。所有照片、清单和索引都留在本机目录里。

## 报告漏洞

如果发现安全问题，请**不要**公开开 issue，改用 GitHub 的私密报告：

1. 打开 <https://github.com/gaoanze/photo-archive-mcp/security/advisories/new>
2. 描述影响范围、复现步骤和建议修复方式。

我们会在 7 天内确认，并在修复后于 CHANGELOG 里说明。

## 使用建议

- 不要把含个人信息的真实实验照片、手机备份目录提交进 issue 或 PR。
- 归档目录如果放进 Git 仓库，请自行确认 `.gitignore` 与远端仓库的可见性。
- 从手机克隆照片时会读取设备文件列表，请在可信设备上使用。
