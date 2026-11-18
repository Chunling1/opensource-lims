# 我的待办、检测领取与报告编制

按 D-139～D-141 完成的首段业务。页面 P-10 接受样品领取、退回和转交。检测样品、检测报告各有一个列表。点击记录进入单条工作表。样品下可创建多份报告，每份报告在自己的工作表完成 PDF 上传、检测日期和审1送审。所有操作写入本地实例。演示包含虚构人员、编号、项目和方法。

登录首页为 P-02「我的待办」。按类型或到达日期筛选后可打开对应记录。领取后尚未建报告的样品计作一项编制待办，建报告后由该份报告接续。池模式和指定模式按当前授权及人员回避筛选。审1待办可查看送审资料，P-12 审核办理和生成被退回任务在后续阶段实现。全局搜索目前为占位。

首页与菜单计数维护在 backend/worklist.py；待办界面在 frontend/src/MyTasks.vue；分页控件在 TaskPager.vue；办理原因弹窗在 ReasonModal.vue。主题色 #405189 集中在 frontend/src/theme.css。升级命令会运行 p02_002，为旧待办从动作历史回填可追溯的到达时间。历史无时间依据的行显示“历史时间未记录”。

## 从源码启动（本仓库）

本项目采用 Apache-2.0，见 LICENSE；第三方组件仍适用各自许可证，见 THIRD_PARTY.txt。
当前为开发中的业务切片，不是完整 LIMS，不构成 CNAS 或其他认证声明。

需要 Python 3.10+、Node.js 22.12+。在仓库根目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv\Scripts\python manage.py upgrade
.venv\Scripts\python manage.py seed-demo
.venv\Scripts\python manage.py serve --port 8878
```

浏览器打开 http://127.0.0.1:8878/ 。演示账号及密码仅供本机试用，不要部署到公网。仓库不包含数据库、上传文件、密钥、wheels 或构建产物。

后续优化采用“修改 → 测试 → commit → push”方式同步；未完成及未经检查的文件不自动推送。

## Windows 离线试用（另行打包的发行包）

环境为 Windows x64、Python 3.10 和 Python 启动器 py。解压完整发行包，双击 `start-demo.cmd`，在浏览器打开 http://127.0.0.1:8878/ 。前端已构建，演示需要的 Python 安装包放在 wheels。启动窗口内按 Ctrl+C 可以停止服务。再次启动保留已办记录。

虚构主账号为 **lin**，密码为 **LimsDemo2026**。首次登录可在待领取池看到“溪流水样”和“河岸测点”。

1. 在“检测样品”列表点击样品编号，领取后选择 BG 编号规则并创建报告。页面自动进入新报告的工作表。随后也可从“检测报告”列表按编号、样品和状态查找，点报告编号继续办理。
2. 在“资料类型”分别选择“原始记录”和“待签报告”，各保存一个 PDF。可以追加多份原始记录，或指定替换其中一份。待签报告每份报告同时保留一个当前版本。
3. 填检测开始、结束日期，例如今天。在“下一办理人”选择沈宁，提交后进入“审1 待办理”。打开同一样品下的另一份草稿可以继续编制。
4. “河岸测点”用现场模板。提交时填写现场检测日期，送审直接进审核池。退回待领取池可在上传第一份资料前试用。已经上传资料的样品可由具备权限的人员转交。

可换用 **zhou** 验证接收后的本人维护，用 **lu** 查看检测授权已到期时的领取池，用 **zi** 查看本部门缺少合格审核人的提醒。演示密码相同。下载文件时服务器会检查当前会话与数据范围。

## 按改动找代码

| 需求 | 主要维护入口 | 可用的核查 |
|---|---|---|
| 改项目与方法的授权覆盖、候选人、回避、冻结或按钮置灰文字 | backend/policy.py | 一个决策同时供详情、动作接口使用。跨部门分配及旧负责人的编辑权见 test_scope_pool_and_transfer、test_cross_department_assignment_and_immutable_audit |
| 改领取、退回池、转交的状态写入和负责人待办 | backend/ownership.py | 两人同时领取、重复提交、转交后换人 |
| 改取号、检测日期、送审资料快照、草稿取消 | backend/reporting.py | 取消号码保留、指定和池模式、独立报告版本 |
| 改 PDF 校验、替换链、只追加的本地文件写入 | backend/documents.py | 原件保留、多个原始记录、审核后拒绝改写 |
| 改并发、重放和动作留痕 | backend/commands.py | 同一操作者和请求编号对应一次动作；失败回滚。样品操作看样品版本，报告操作看该份报告版本 |
| 改列表查询、筛选、分页和详情返回的字段 | backend/views.py | 两个视图用数据库查询；前端数据类型在 frontend/src/api.ts |
| 改会话、HTTP 入参、下载或运行配置 | backend/app.py | Flask 同源接口。PDF 上限用 LIMS_PDF_MB 设置，默认 50 MiB |
| 改字段或表 | backend/schema.py，backend/migrations/versions/ | 首次交付为 p10_001，已交付后新增迁移。SQLAlchemy 表供运行时使用，Alembic 旧迁移保留自己的结构快照 |
| 改样品及报告列表、筛选和分页 | frontend/src/Detection.vue | 页面为 P-10。Tabler 提供卡片、表单、按钮、栅格与状态样式 |
| 改报告编制、文件选择和送审表单 | frontend/src/ReportEditor.vue | 页面为 P-11。Tabler 从 frontend/src/main.ts 导入，业务样式文件为零 |
| 改样品领取、转交、关联报告和工作表导航 | frontend/src/Worksheet.vue 与 router.ts | 列表筛选和页码保存在地址栏，支持刷新与返回 |
| 改虚构数据或替换演示账号 | backend/demo.py | manage.py seed-demo 仅在账号表为空时初始化 |

## 数据与开发命令

`instance/demo.db` 保存 SQLite 数据，`instance/files/` 保存追加的 PDF，`instance/session.key` 保存本实例的会话签名密钥。演示启动时生成这三项。正式文件存储方式待产品决策。本次文件编号取自数据库原子更新。文件、负责人变更、送审快照、审计和待办由同一个业务动作协调写入。

从产品根目录运行。以下命令默认使用已经安装 requirements.txt 的 Python 环境。

```powershell
python manage.py upgrade
python manage.py seed-demo
python manage.py serve --port 8891
python -m unittest discover -s tests -v
```

使用 PostgreSQL 时设置 `LIMS_DATABASE_URL` 为 `postgresql+psycopg://账号:密码@主机:端口/库名`，再执行 upgrade。seed-demo 供空的试用库使用。用 `LIMS_INSTANCE` 选择文件和密钥目录。数据库回归可将 `LIMS_TEST_POSTGRES` 指向独立测试库，测试会在其中新建并清理自己的 schema。Windows 离线启动脚本固定使用 SQLite，配置 PostgreSQL 时使用上述命令。

前端开发从 frontend 目录执行 `npm ci` 和 `npm run build`。Vite 开发模式用 `npm run dev` 并将 API 代理到 8876，后端相应使用 `python manage.py serve --port 8876`。正式构建的 dist 由 Flask 同源提供。

## 交付边界

当前可重复验证 P-02、P-10/P-11 及审1待办的生成。委托登记与评审结果、收样确认、人员权限与模板版本由演示种子提供。后续阶段仍需交付上游维护页面、P-12 的实际审核和批准、签章与发放，以及列表导出、备份恢复。开源许可证为 Apache-2.0（用户选择）；正式产品名称仍待定。运行时前端的第三方声明见 THIRD_PARTY.txt。
