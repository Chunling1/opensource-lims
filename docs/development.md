# 开发与测试

## 本地开发

先按根目录 README 安装依赖、升级数据库并初始化虚构数据。

后端：

```sh
python manage.py serve --port 8876
```

另一个终端：

```sh
cd frontend
npm run dev
```

Vite 将 `/api` 代理到 8876。构建后可由 Flask 同源提供 `frontend/dist`，无需分别部署前后端。

## 运行配置

| 环境变量 | 用途 |
| --- | --- |
| `LIMS_INSTANCE` | 实例目录，保存数据库、文件和会话密钥 |
| `LIMS_DATABASE_URL` | SQLAlchemy 数据库连接；不设置时使用实例目录下 SQLite |
| `LIMS_PDF_MB` | 上传 PDF 大小上限，默认 50 MiB |
| `LIMS_TEST_POSTGRES` | 独立回归测试数据库连接 |

PostgreSQL 配置示例（占位值需替换，不要提交真实连接）：

```powershell
$env:LIMS_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/lims_dev'
python manage.py upgrade
python manage.py seed-demo
```

Linux / macOS 用 `export LIMS_DATABASE_URL='...'`。需先创建数据库；`seed-demo` 仅用于空的试用库。

## 自动化验证

在仓库根目录、已激活的 Python 环境中：

```sh
python -m unittest discover -s tests
python -m unittest discover -s acceptance -t .
```

设置 `LIMS_TEST_POSTGRES` 后重复以上命令，即可核查 PostgreSQL 分支。测试会创建和清理 schema，**禁止使用生产连接**。独立测试使用应用工厂及数据库辅助设施，并非完全不接触内部实现的黑盒测试。

前端检查：

```sh
cd frontend
npm ci
npm run build
```

页面测试见 [acceptance/ui/README.md](../acceptance/ui/README.md)。脚本使用 Edge，必须使用全新的临时实例；流程测试和截图脚本分别重新初始化数据库。页面脚本会领取样品、上传和送审，不能对真实业务数据执行。

CI 不代替浏览器视觉检查。目前 CI 不运行 Edge 页面流程；页面布局、日期弹层和移动端交互需要单独核验。

## 常见问题

- **首页不可用或静态资源缺失**：先在 frontend 执行 `npm ci && npm run build`。
- **演示记录和初次不同**：种子初始化不会清空已存在数据。要重新试用，停止服务并选择一个新的 `LIMS_INSTANCE`；不要删除仍需保留的实例。
- **Vite API 请求失败**：确认后端在 8876；同源构建启动示例则使用 8878。
- **文件句柄 ResourceWarning**：下载文件测试中曾出现该警告；不应将“测试通过”描述为“无警告”，需单独跟踪修复。
- **生产部署**：目前没有经过完整验证的生产部署、备份恢复或运维方案，不提供生产就绪保证。

## 修改约定

业务核查集中在后端；调整字段时新增迁移，不重写已交付迁移。前端优先使用 Tabler 结构与组件，不复制来源不清的商业模板。新增依赖需核对许可并更新第三方声明。
