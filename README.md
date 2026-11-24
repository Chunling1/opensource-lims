# Open-LIMS (Tabler Edition)

开源实验室信息管理系统（LIMS），基于 **Vue 3 + TypeScript + Tabler (MIT)** 前端与 **Python Flask + SQLAlchemy** 后端构建，采用 **Apache-2.0** 开源许可协议。

## 目录结构

- `backend/`：Flask + SQLAlchemy 后端服务（支持 SQLite 开箱即用，也可通过 `DATABASE_URL` 切换至 MySQL / PostgreSQL）
- `frontend/`：Vue 3 + TypeScript + Pinia + Tabler UI 前端工程
- `LICENSE`：Apache-2.0 开源许可证
- `THIRD_PARTY.txt`：第三方依赖与字体许可清单

## 核心功能模块

1. **组织架构与人员权限管理**：支持部门分组、角色权限配置、Excel 模板下载与批量导入/导出。
2. **质量体系管理**：
   - **设备台账**：支持设备档案维护、检定校准状态追踪、Excel 模板下载与批量导入/导出。
   - **检测标准库**：内置「检测参数」字段，支持标准与参数一体化 Excel 导入/导出及业务流自动带出。
3. **委托到报告全流程**：
   - 委托登记 → 样品登记 → 合同评审 → 样品入库/出库（可配置跳过） → 检测数据录入 → 多级审核/多级批准（含退回、撤回、更正） → 线下/线上签发 → 归档发放。
4. **系统配置**：
   - **项目流程配置**：按项目维度灵活配置是否跳过入库/出库、以及多级审核与多级批准节点。
   - **电子签章自助配置**：支持在线配置 e签宝 AppID / Secret / 印章参数，未配置或关闭时自动支持线下签发与归档。
   - **Word 模板字段映射管理**：支持在线查看和管理报告/委托单模板映射。

## 快速启动（本地开发 / 评估）

### 1. 启动后端（Python 3.11+，默认端口 `5100`）

> 后端依赖 Python 3.11+（使用了标准库 `datetime.UTC`），默认将 SQLite 数据库创建在 `backend/instance/inspection.db`。

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

设置管理员初始密码（请自行设置符合强密码要求的密码）并启动服务：

```bash
# Windows (PowerShell)
$env:ADMIN_PASSWORD = "<请自行设置强密码>"
$env:JWT_SECRET = "<请自行设置随机密钥>"
python run.py

# macOS / Linux
export ADMIN_PASSWORD="<请自行设置强密码>"
export JWT_SECRET="<请自行设置随机密钥>"
python run.py
```

首次启动时会自动在 `backend/instance/` 下初始化 SQLite 数据库并写入演示用基础数据。

### 2. 启动前端（默认端口 `5189`）

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5189`，使用 `admin` 与您设置的 `ADMIN_PASSWORD` 登录。

## 字体说明

本开源仓库不包含任何商业/专有字体（如微软宋体、黑体、Times New Roman）。生成 PDF 时，后端会自动检测并使用操作系统已安装的字体或开源字体（如思源宋体/思源黑体、Liberation）。您也可以通过环境变量自定义字体路径：

- `PDF_PAGE_NUMBER_SIMSUN_FONT_PATH`（中文字体路径）
- `PDF_PAGE_NUMBER_TIMES_FONT_PATH`（英文字体路径）

## 测试与构建验证

```bash
# 前端：模板规范检查 + 类型检查 + 生产构建 + 平台单元测试
cd frontend
npm run build
npm run test:platform

# 后端：单元测试
cd backend
pytest
```
