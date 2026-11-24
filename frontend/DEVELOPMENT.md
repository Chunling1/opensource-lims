# 开发与交付说明

## 模板复用对应

| 业务区域 | 模板来源（相对 `docs/HTML/Master/src`） | Vue 实现 |
| --- | --- | --- |
| 页面框架与菜单 | `partials/main.html`、`menu.html`、`sidebar.html`、`topbar.html`、`footer.html` | `App.vue`、`AppSidebar.vue`、`AppTopbar.vue` |
| 面包屑与标题 | `partials/page-title.html` | `PageHeading.vue` |
| 主题设置 | `partials/customizer.html`、`assets/js/app.js` | `ThemePanel.vue`、theme store |
| 首页工作台与我的待办 | 空白内容页，保留标题与面包屑 | `MenuPage.vue` |
| 样品列表及筛选 | `apps-ecommerce-orders.html` | `SampleListView.vue` |
| 样品登记及编辑 | `forms-layouts.html` | `SampleFormView.vue` |
| 详情与记录 | `apps-ecommerce-order-details.html` 的卡片布局及模板 `acitivity-timeline` | `SampleDetailView.vue` |

列表和表单改为实验室中文内容，移除模板购物车、多语言入口等无关功能。图标继续使用模板的 Remix Icon、MDI 和 Boxicons 字体。

公共 `DataTable` 的 `stickyActions` 默认为 `true`：提供 `actions` 插槽时，最后一列的表头和单元格固定在横向滚动容器右侧。具体表格可设置 `:sticky-actions="false"` 恢复随内容滚动；无操作插槽不增加列。使用模板现有定位、层级和背景工具类，不添加左侧分隔线；操作列表头使用 Remix Icon 菜单图标，保留悬停与选中行效果，操作菜单仍由浮层呈现。`/#/components` 的“公共表格固定操作列”示例可验证开关、动态列、空数据、分页及加载状态；不修改未使用该组件的手写表格。

委托管理中的合同、单位单选、检测方案及子项目通过 `SingleChoice.vue` 统一呈现方框勾选外观，使用模板圆角、背景、字号和勾选图标，不新增 CSS。底层保留原生 `type="radio"` 及原有 `name`、ID/label 关联，因此仍只能选择一项，支持方向键和焦点提示；业务多选继续使用 checkbox。新增单选位置可复用该组件，不能将单选状态改为多值数组。

顶部与侧栏用户区域通过 `UserMenu.vue` 复用模板原有头像、名称、角色/在线状态及下拉菜单结构，头像直接引用本地 `avatar-1.jpg`。保留模板“显示侧栏用户时隐藏顶部用户”的规则。个人资料和帮助使用模板弹窗，设置入口打开主题面板。消息中心进入演示通知；用户菜单提供演示身份切换和工作空间锁定，不保留待办样品及模板钱包入口。

顶部恢复模板快捷应用网格、全屏、明暗切换、通知下拉和手机搜索结构。快捷应用使用现有路由；通知下拉和通知中心共用 `demoNotifications` 演示消息及 `NotificationMessages` 展示组件，提供标题、完整正文和时间，不含页面跳转。通知数量不再代表待接收样品数量，也不依赖样品或审批查询。Bootstrap 下拉实例与全屏事件随组件生命周期清理，不加载旧版模板脚本。

## Bootstrap 升级与样式来源

原模板依赖 Bootstrap 5.3.6，新工程锁定 **5.3.8**。模板的 `bootstrap.scss` 会注入 `vz-` 变量前缀、颜色、尺寸与扩展工具类，不能替换成官方默认编译 CSS。

构建流程：

1. 读取原模板 SCSS，Sass `loadPaths` 指向根工程，解析原有 `./node_modules/bootstrap/...` 导入。
2. 编译 `bootstrap.scss`、`app.scss`、`custom.scss`，不修改其变量或添加新的视觉规则。
3. 原样复制 `icons.min.css`、字体和图片，并生成包含源码、复制文件与编译输出 SHA-256 的 `public/template/manifest.json`。
4. 顺序加载 Bootstrap、图标、应用主题、模板 custom CSS。
5. Vue 按需导入新 Bootstrap 的 Modal、Offcanvas、Dropdown、Collapse、Tooltip、Popover、Toast 及所需 Popper 依赖，不加载旧 Bootstrap 或模板 app.js/layout.js。
6. SimpleBar 6.3.1 和 Waves 从原模板 dist 原样复制并校验哈希，通过本地静态脚本加载。Vue 管理滚动组件挂载与销毁，关闭 SimpleBar 自动 DOM 观察器；样式继续使用模板 app.scss 中已有的插件规则。构建提示这些原样复制的脚本不参与打包是预期行为，生产目录直接提供这些资源。

为满足 Vite 的 Sass peer dependency，编译器由模板的 1.69.5 调整到 **1.77.8**。模板源码无需补丁即可编译；Sass 的模板遗留警告在独立编译器中静默，实际编译错误仍会终止构建。

Bootstrap 官方 5.3.8 包含颜色对比算法、spinner 布局和下拉焦点等修复；因此输出 CSS 不与旧版逐字相同，也不承诺旧版每个像素保持不变。验收以模板变量、组件结构和主题视觉一致性为准。未新增视觉兼容补丁。升级记录：[Bootstrap 5.3.8](https://github.com/twbs/bootstrap/releases/tag/v5.3.8)。

原模板 SCSS 不变；构建时仅将原有 Poppins 外站导入地址映射至 public/fonts/poppins.css。Google Fonts 返回的字体声明及字体已下载到本地，许可证随资源保存；不增加视觉规则。默认 HKGrotesk 和图标字体仍来自模板原始资源。主题设置完整复用原模板的 53 个控件：图片卡片、布局与菜单示意图、定位分段按钮、头像开关、渐变色展开区、背景缩略图、主色色块及预加载动画。保留原有排列、class 和样式依赖的 ID/for，添加 Vue 状态绑定与键盘操作，文案中文化；底部模板购买入口改为关闭按钮。设置抽屉和常规侧栏使用 TemplateScroll 封装的 SimpleBar，保留 Vue 内容节点的父级，避免插件移动节点影响 Vue 更新；不适用的菜单布局退回原结构。

公共框架恢复返回顶部、滚动阴影、桌面浮动设置入口、菜单 Collapse 动画与弹窗 fade。顶部搜索通过 registrationDemo.samples 的委托查询接口按样品编号或名称检索，沿用委托查询的日期范围及后端权限。建议进入正式样品详情，查看全部进入委托查询的全部样品列表，编号或名称条件可见、可移除，并随详情返回和刷新保留。保留页面搜索、最近搜索、键盘选择及加载/空/失败状态；最近搜索独立保存在 lims.search.v1。旧样品页和通用业务页及其专用组件、路由均已删除；底层业务服务与数据不变。

主题预览图全部从本地加载：7 张复用模板 `images/demos` 的原始资源；Corporate、Galaxy、Classic、Vintage 的 4 张缺失资源已从模板原链接下载到 `public/theme-previews`。下载来源及 SHA-256 记录在 `src/assets/theme/preview-sources.json`，由样式校验脚本验证。官网后两张资源虽使用 `.png` URL，实际是 JPEG，因此原样保存为 `.jpg`。`node scripts/fetch-theme-previews.mjs` 仅用于主动刷新缺失预览资源，常规构建无需联网，也不改写 docs。

模板的粗体 HKGrotesk 存在旧 EOT 文件缺失，但同一 `@font-face` 后续的 WOFF `src` 已覆盖旧声明。现代浏览器实际请求的 WOFF 文件齐全。资源检查按最终生效的 `src` 校验，不改写模板，也不伪造 EOT 文件。

## 主题配置与菜单

`ThemeSettings` 是设置面板、存储和 DOM 映射的统一类型。偏好存储为 `lims.theme.v1`，包含版本号和配置；损坏或不支持的配置回退为默认值。保存失败会在设置面板显示提示，当前页面仍可切换。

| 配置 | 属性 |
| --- | --- |
| 布局、主题、明暗 | `data-layout`、`data-theme`、`data-bs-theme` |
| 主色、顶部栏 | `data-theme-colors`、`data-topbar` |
| 宽度、定位、侧栏视图 | `data-layout-width`、`data-layout-position`、`data-layout-style` |
| 侧栏颜色、尺寸、背景、可见性 | `data-sidebar`、`data-sidebar-size`、`data-sidebar-image`、`data-sidebar-visibility` |
| 页面背景、预加载、用户头像 | `data-body-image`、`data-preloader`、`data-sidebar-user-show` |

联动规则：

- 双列与 Semi Box 使用流式宽度；分离视图只适用于垂直布局。
- 盒式宽度联动悬停展开菜单，恢复流式时恢复标准尺寸。
- 水平布局隐藏侧栏专用选项；双列布局隐藏尺寸、定位和宽度选项。
- Semi Box 隐藏侧栏时同步去除有效侧栏属性，但保留用户偏好，恢复显示后重新应用。
- Galaxy 有效模式与侧栏均为深色，其他主题的明暗偏好保留；页面背景仅在 Galaxy 生效，背景一不叠加侧栏图片。
- Galaxy 面板显示有效的深色选中状态并禁用不适用项，切回其他主题恢复保存的偏好。页面标题使用模板 bg-galaxy-transparent 类。
- 悬停菜单固定展开使用 sm-hover-active，保持取消固定按钮可见；固定为临时状态，不把用户保存的 sm-hover 改成 lg。
- 小于 768px 时双列暂时使用垂直布局；平板按模板断点收起侧栏，不覆盖持久化的桌面配置。
- 恢复默认只重置主题配置。主题和导航切换不修改样品数据；主题设置不重建 RouterView，不清空表单。

## 样品数据与后端接入

当前 `sampleService` 的公开方法为：

```ts
list(query?: SampleQuery): Promise<{ items: Sample[]; total: number; page: number; pageSize: number }>
detail(id: string): Promise<Sample>
create(input: SampleInput): Promise<Sample>
update(id: string, input: SampleInput): Promise<Sample>
receive(id: string): Promise<Sample>
returnSample(id: string, reason: string): Promise<Sample>
resubmit(id: string): Promise<Sample>
statistics(): Promise<{ total: number; pending: number; received: number; returned: number }>
```

样品直接使用当前 IndexedDB 结构，不提供旧版存储读取或数据迁移。演示编号为 `SP + UTC 日期 + 当日序号`，ID 为 UUID；日期保存为 ISO 字符串，界面按本地时间显示。操作人来自当前有效演示身份。首次初始化覆盖三种状态，保存失败不写入成功状态；数据损坏时不自动覆盖已有内容。

后端接入时保留上述 Promise 返回形状，替换服务层为 HTTP 实现；字典可通过服务加载后注入表单。后端需要承担鉴权、唯一编号、状态转换、并发校验和审计记录的最终验证。真实接口路径、认证及错误协议待后端契约确定，本期不虚构这些协议。

当前浏览器数据不提供跨设备共享或不可篡改审计。跨标签页写入通过 IndexedDB 事务串行化，记录版本用于避免旧表单覆盖。客户端权限仅用于演示，真实部署必须接入后端鉴权。

## 初始版本验证记录（完整扩展见 LIMS_IMPLEMENTATION.md）

- 19 项单元测试覆盖字段验证、完整状态流程、非法转换、编号唯一性、查询统计、存储失败、成功写入通知和主题约束。
- 17 项浏览器测试覆盖业务流程及公共框架：包含原模板设置控件与头像结构对照、四布局、主题偏好、样品写入后的待办刷新、搜索建议、滚动条、悬停固定、Galaxy 有效状态、提示层清理及弹窗过渡。
- 浏览器截图覆盖默认工作台、深色双列、Galaxy Semi Box 及手机样品列表；已检查内容布局、图标、背景和表格横向滚动。
- `check:styles` 再次编译样式比对哈希，校验本地 CSS URL 指向的文件真实存在，同时扫描禁止业务样式。
- `test:production` 将 `dist` 独立挂载至 `/lims/`，验证子目录资源、Hash 路由、刷新、主题持久化及 Bootstrap 弹窗。
- 浏览器测试由 global setup 直接创建和关闭 Vite 服务，避免 Windows 上结束 npm 子进程树时挂起；已有本项目开发服务器时可复用。

后续增加模块时，先在原模板中找到相应组件或工具类，再添加路由与菜单项；所有新增数据操作继续通过服务层。


## 完整业务前端扩展

业务配置在 src/services/business/modules.ts，集中声明表单字段、引用关系、状态动作和岗位。BusinessView 复用模板卡片、表格、表单与弹窗；具体业务规则在 limsService 中执行，界面不能越过规则直接变更状态。Flatpickr 中文日期与 Choices 多选从模板 dist 原样复制，组件销毁时释放实例。

IndexedDB repository 提供 read/write。write 回调必须同步，异常回滚，只有 transaction.oncomplete 后发出本页及 BroadcastChannel 变更事件。普通记录使用版本乐观锁。签发报告先在快照计算状态和生成 PDF，提交前校验数据库 revision，确保 PDF 失败或并发更新时不出现虚假签发。

报表使用本地 Noto Sans CJK SC 字体（SIL OFL），pdfmake 延迟加载；网页仍严格使用模板 CSS。报告字体、表格、页边距等属于 PDF 文档定义，不是新增网页业务样式。签发文件作为 Blob 归档，后续下载直接读取归档文件；新模板版本不修改旧报告。

sampleService 直接使用 IndexedDB 仓储；样品初始资料、部门、版本和业务引用在 seedDatabase 中统一生成。单元测试覆盖实际样品服务的事务、状态、权限和失败处理。新项目不保留旧版 localStorage 样品服务、迁移标记或旧存储事件监听。

服务替换边界：保留领域数据与动作语义，将 repository 或异步领域服务替换为后端实现；后端必须自行执行身份认证、数据范围、状态、版本和事务校验，不能信任前端检查。本期没有预设 URL、HTTP 方法或服务端数据库表结构。

菜单最多三级，水平布局按视口将末端分组纳入模板 More（更多）结构；超出右边界时使用模板 dropdown-custom-right 类。角色隐藏菜单同时服务层拒绝越权，快捷入口与搜索按可读模块筛选。
