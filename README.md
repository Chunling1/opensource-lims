# Open-source LIMS

[![CI](https://github.com/Chunling1/opensource-lims/actions/workflows/ci.yml/badge.svg)](https://github.com/Chunling1/opensource-lims/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

面向实验室业务的开源 LIMS 基础项目，从**样品领取、报告编制与送审**这一条业务链开始。

**Flask · SQLAlchemy · Vue 3 · TypeScript · Tabler · Apache-2.0**

[快速开始](#快速开始) · [开发与测试](docs/development.md) · [实现说明](docs/implementation.md) · [参与贡献](CONTRIBUTING.md) · [更新日志](CHANGELOG.md) · [安全反馈](SECURITY.md)

> **开发中，尚非完整 LIMS。** 当前适合本机试用、代码评估和参与开发，不建议直接投入生产。项目不构成 CNAS 或其他认证声明，也不替代实验室的质量管理程序。

## 现在能做什么

| 业务 | 当前实现 |
| --- | --- |
| 我的待办 | 类型和日期筛选、计数、打开办理记录 |
| 检测样品 | 待领取池、本人负责列表、样品工作表 |
| 责任交接 | 领取、退回、转交；后端核查授权、版本与冻结状态 |
| 报告编制 | 一个样品创建多份报告，保留独立状态和版本 |
| 检测资料 | 原始记录与待签报告 PDF 上传、替换、受控下载 |
| 提交审核 | 日期校验、审核人选择或进入审核池、送审资料快照 |
| 操作反馈 | 置灰原因、办理原因弹窗、冲突提示、动作记录 |

**暂未实现：**完整委托与收样维护、实际审核批准、签章发放、导出、备份恢复等。演示中的上游资料及授权由种子数据提供；全局搜索为禁用占位。详见[范围与方向](docs/roadmap.md)。

## 快速开始

### 环境

- Python 3.10 或更高版本
- Node.js 22.12 或更高版本，npm
- Git
- 默认 SQLite，无需额外数据库；也支持 PostgreSQL

### 获取代码与安装依赖

```sh
git clone https://github.com/Chunling1/opensource-lims.git
cd opensource-lims
python -m venv .venv
```

激活虚拟环境，二选一：

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# Linux / macOS
source .venv/bin/activate
```

如果 PowerShell 不允许激活，可以在后续命令中用 `.venv\Scripts\python.exe` 替代 `python`，无需修改系统执行策略。

```sh
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python manage.py upgrade
python manage.py seed-demo
python manage.py serve --port 8878
```

打开 **http://127.0.0.1:8878/**。服务仅监听本机地址；按 Ctrl+C 停止。再次启动会保留数据。

> 仓库仅提供源码，不包含 `dist`、Python wheels 或数据库。`start-demo.cmd` 面向另行打包的离线发行包，不是源码首次启动入口。目前未提供正式发行包或公共在线演示。

### 演示账号

所有账号的演示密码均为 `LimsDemo2026`，数据和人员均为虚构。

| 账号 | 演示角色 / 用途 |
| --- | --- |
| `lin` | 林澄，领取与编制 |
| `zhou` | 周禾，协作与转交 |
| `shen` | 沈宁，审核待办 |
| `lu` | 陆川，授权到期场景 |
| `zi` | 顾桐，资料管理员视角 |

建议从 `lin` 登录：我的待办 → 检测样品 → 领取样品 → 创建报告 → 上传两类 PDF → 填写日期 → 提交审核。审核角色当前可查看送审资料，尚不能完成后续审核批准。

**不要将演示账号、种子数据和演示配置直接暴露到公网。** `instance/` 保存数据库、上传文件和会话密钥，不应提交到 Git。

## 项目结构

```text
backend/             Flask API、业务规则、模型与数据库迁移
frontend/src/        Vue 3 + TypeScript + Tabler 页面
acceptance/          独立业务回归与页面测试
tests/               产品单元与集成测试
docs/                开发、实现与范围说明
.github/             CI、Issue 与 PR 模板
manage.py            数据库升级、演示初始化和本机启动入口
```

业务动作与可办理原因由后端统一计算；列表筛选和分页在 API 中执行。前端不重复实现授权判断。SQLite 用于本机试用，PostgreSQL 用于数据库回归和后续部署评估。

## 开发与验证

```sh
python -m unittest discover -s tests
python -m unittest discover -s acceptance -t .
cd frontend
npm ci
npm run build
```

[开发说明](docs/development.md)包含 PostgreSQL 配置、页面测试和常见问题。GitHub Actions 执行后端回归及前端构建；以[实际运行结果](https://github.com/Chunling1/opensource-lims/actions)为准。自动化测试不等于视觉验收或生产就绪。

## 参与维护

- 问题与建议：[提交 Issue](https://github.com/Chunling1/opensource-lims/issues/new/choose)，请勿附真实客户资料、检测报告或凭据。
- 修改代码：先阅读[贡献指南](CONTRIBUTING.md)，业务规则变更应先讨论，避免在界面优化中悄悄改变规则。
- 安全问题：使用[私密漏洞报告](https://github.com/Chunling1/opensource-lims/security/advisories/new)，不要公开可利用细节。
- 更新记录：[CHANGELOG.md](CHANGELOG.md)。当前没有固定发布周期或服务响应承诺。

## 许可证与致谢

本项目采用 [Apache License 2.0](LICENSE)。第三方组件保留各自许可证，见 [THIRD_PARTY.txt](THIRD_PARTY.txt)。

感谢 [Flask](https://github.com/pallets/flask)、[Vue](https://github.com/vuejs/core)、[Tabler](https://github.com/tabler/tabler) 等开源项目。仓库文档组织参考 Flask 与 Tabler 的公开项目结构，业务实现和维护说明以本仓库实际状态为准。
