# 前端目录约定

顶层只保留 7 个有实际用途的目录。优先复用现有目录，不为少量文件或尚未开发的模块创建新的顶层目录。

```text
src/
├── assets/                   # 源码引用的资源清单；原模板图片和字体仍在 public/
├── components/
│   ├── common/               # 公共组件、组合式函数及模板指令
│   ├── layout/               # 工作空间布局、顶栏、导航、主题面板
│   ├── business/             # 通用业务表单与表格
│   └── commissions/          # 委托登记专用表单、选择器、附件、查询等
├── router/
│   ├── index.ts              # 路由入口、滚动策略
│   ├── guards.ts             # 权限与导航异常处理
│   ├── modules/              # 按业务拆分的路由
│   └── navigation/           # 菜单配置
├── services/
│   ├── common/               # 通用错误处理、公式计算
│   ├── business/             # 通用业务服务、模块配置、字典、导入导出
│   ├── commissions/          # 委托 HTTP 接口、业务规则、列定义
│   ├── samples/              # 当前样品业务服务
│   ├── reports/              # 原有报告 PDF 服务
│   └── storage/              # 数据仓储和共享演示身份
├── stores/                   # 当前身份、锁屏、全局错误状态
│   └── theme/                # 主题 store、启动、设置和资源访问
├── types/                    # 通用及样品类型、第三方声明
│   └── commissions/          # 委托表单、登记和打印接口类型
├── views/                    # 仅放路由页面，按业务分类
│   ├── commissions/
│   ├── samples/
│   ├── business/
│   ├── workspace/
│   ├── errors/
│   └── development/
├── App.vue                   # 初始化、根错误边界、布局切换
├── main.ts                   # Vue、Pinia、Router 启动入口
└── README.md
```

## 放置规则

- 新模块页面放在 `views/<模块>/`，业务组件放在 `components/<模块>/`，接口及业务代码放在 `services/<模块>/`。需要共用的类型放在 `types/` 对应模块中。
- HTTP 适配器使用 `*Api.ts`，业务服务使用 `*Service.ts`。委托适配器为 `services/commissions/registrationApi.ts`，现有导出名 `registrationDemo` 保持兼容。
- 页面自己使用的状态留在页面；只有跨页面共享状态才放进 `stores/`。公共组合式函数沿用 `use*.ts` 命名，放在 `components/common/`。
- 新路由放在 `router/modules/`，菜单在 `router/navigation/`。不改变已有 URL、接口路径、存储键和权限规则。
- 功能不足以独立成组时不增加中间文件夹；例如委托组件和页面已直接放在 `commissions/`，不再嵌套一层 `registration/`。
- HTTP 模拟后端继续放在根目录 `server/`；不要把服务端分页查询搬到前端，也不要将 Node 端代码放入浏览器目录。
- 原版模板资源、字体、预览图继续位于 `public/`；不新增 CSS、内联样式或修改原模板 SCSS。

## 本次清理

- 顶层目录由 14 个合并为 7 个；原 `api`、`config`、`composables`、`directives`、`mocks`、`theme`、`utils` 的有效代码已归入上述目录。
- 公共反馈与模板组件合并到 `components/common/`；主题面板归入布局组件；删除合并后留下的空目录。
- 原 `Root.vue` 成为 `App.vue`，工作空间布局移至 `components/layout/WorkspaceLayout.vue`，消除两个顶层应用组件造成的混淆。
- 删除没有路由入口、也没有任何源码或测试引用的 `DashboardView.vue`、`ForbiddenView.vue`、`NotFoundView.vue`。工作台和我的待办使用 `MenuPage.vue` 空白页，403/404 页面仍由 `ErrorView.vue` 统一提供。
- 委托管理的五个菜单页面使用完整的路由组件映射，删除不可达的 `CommissionPage.vue` 占位页。附件仅在列表弹窗中管理，移除旧的新建表单附件分支；操作弹窗删除已停用的更改字段及传参，同时清理无引用的状态标签和列解析导出。
- 样品和检测菜单使用完整的路由组件映射，删除不可达的 `SamplePage.vue`、`TestingPage.vue` 和旧 `OriginalElnPicker.vue`；检测菜单已接入正式页面。清理无调用的前端 ELN 实时查询方法、表单辅助函数、类型别名及导入；保留当前 ELN 选择器使用的查询方法，以及后端接口和测试。
- 按菜单及其页面操作的可达性，删除无入口的 `LabelsView.vue` 和 `/labels` 路由、已被新版申请列表替代的 `ReportChangeRequestView.vue` 及其专用前端方法，以及已由详情页报告预览替代的 `/testing/data-check/:id/report` 路由和专用分支。保留样品关联使用的通用业务页和必要的错误、重定向路由。
- 首页移除审批任务菜单、`/approvals` 路由及残留入口，清除 `OperationsView.vue` 中旧工作台统计和审批任务逻辑；保留通知中心、演示身份切换，以及其他模块的业务审批流程。
- 报告菜单使用明确的正式组件映射，删除未使用的 `ReportPage.vue`。顶部搜索迁移至委托查询接口及正式样品详情，删除旧 `SampleListView.vue`、`SampleFormView.vue`、`SampleDetailView.vue`、`BusinessView.vue` 及专用组件、路由助手、返回缓存和旧模块守卫；旧 `/samples` 列表、新增、详情、编辑及全部 `/workspace/*` 业务路由不再提供页面，后端业务数据及服务不变。
- 本项目为新开发项目，不保留历史数据读取和迁移兼容层。样品直接使用当前 IndexedDB 仓储，初始模拟数据在 `seedDatabase` 中生成；旧版样品服务、迁移标记及旧存储监听已删除。

移动或删除文件后，执行类型检查、单元测试、构建、样式检查及相关浏览器测试，同时更新模拟后端、脚本和测试中的引用。
