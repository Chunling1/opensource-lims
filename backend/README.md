# 示例国检院检测系统 — 后端

按《检测信息系统后台开发说明》实现的 Flask 后端，与前端 Vue 原型联调。

## 技术栈

- Python 3.10+（开发用 3.12）
- Flask 3.x + Flask-SQLAlchemy 2.0 + Flask-CORS
- OAuth2 资源所有者密码模式（JWT 访问令牌，PyJWT）
- 开发库 SQLite；生产经 `DATABASE_URL` 切换 MariaDB/MySQL/PostgreSQL/达梦/人大金仓/GaussDB（SQLAlchemy 抽象层）

## 运行

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
.venv/Scripts/python run.py                                # 启动于 http://127.0.0.1:5000
```

首次启动自动建表并灌入种子数据（10 账号 + 6 报告 + 仪器/资质/标准），数据落在 `inspection.db`。
删除该文件可重置。所有演示账号密码均为 `123456`。

## 权限模型（规格 2.1）

| 维度 | 落地 | 接口体现 |
|---|---|---|
| 功能授权（菜单/页面） | `permissions[]` | 登录返回，前端据此渲染菜单/页面 |
| 审批事项授权（操作） | `actionPermissions[]` | 登录返回，前端据此渲染按钮，流转接口二次校验 |
| 数据授权（站点/部门，最小颗粒度部门） | `dataScope` | `/api/reports/query` 按范围过滤 |
| 项目授权（检测项目+工作流步骤） | `projectPermissions[]` | 登录返回（扩展字段） |

部门多级（`departments.parent_id`），子部门是父部门子集。

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 账号密码换 JWT，返回前端 AuthResponse 契约 |
| GET | `/api/auth/profile` | 凭令牌取当前用户权限画像 |
| POST | `/api/reports/query` | 报告清单（按数据授权过滤） |
| GET | `/api/reports/<no>` | 报告详情（委托/样品/实验/原始记录+三组校验+附件） |
| POST | `/api/reports/<no>/action` | 报告流转（pass/return，校验审批事项授权） |
| GET | `/api/quality/instruments/<code>/validity?at=YYYY-MM-DD` | 仪器按指定时间的有效性（规格 2.6） |
| GET | `/api/quality/qualifications/<id>/validity?at=YYYY-MM-DD` | 资质历史快照按时间查询 |
| GET | `/api/quality/standards` | 标准库（CNAS/CMA 归属、是否过期） |

## 测试

```bash
.venv/Scripts/python test_integration.py    # 28 条 API 联讯测试
```

## 与前端联调

前端默认走内置 mock。接入真实后端：

```bash
# 1) 起后端
backend/.venv/Scripts/python run.py
# 2) 前端 backend 模式（Vite 代理 /api → 127.0.0.1:5000）
npm run dev -- --mode backend
```

`--mode backend` 加载 `.env.backend`（`VITE_USE_BACKEND=1`）。
前后端联讯端到端测试见 `scripts/e2e-backend.mjs`。
