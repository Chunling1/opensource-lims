# AJ-Captcha 官方 Vue 3 组件

来源：[anji-plus/captcha](https://github.com/anji-plus/captcha/tree/9188ae31cad1b2041277f04351cde4bf78a01fc4)，固定提交 `9188ae31cad1b2041277f04351cde4bf78a01fc4`，Apache-2.0（见 LICENSE）。

- `components` 来自 `view/vue3/src/components/verifition`。
- `images` 来自 `core/captcha/src/main/resources/defaultImages/jigsaw`，保留官方 7 张底图和 6 个透明拼块模板。
- `upstream-manifest.json` 记录原始文件的 SHA-256；`local-manifest.json` 记录适配后的摘要；`integration.patch` 记录源码差异。`npm run check:styles` 同时验证这些本地资源没有发生未记录的修改。

直接使用官方 Verify / VerifySlide / VerifyPoints 的滑块、点选及校验逻辑，外观通过现有模板样式适配，没有自行仿写验证码组件。以下是为现有应用所做的适配：

1. 通过 Vue provide/inject 接入本地模拟 get/check 接口，替换示例服务器请求；保留原有 AES 工具，直接依赖 CryptoJS。
2. 原版 CSS 限定于 `.aj-captcha-native`，避免通用图标和提示类影响业务页面；业务目录不添加 CSS。
3. `fixed` 模式由现有 BootstrapModal 管理关闭和焦点，不在验证成功时刷新并撤销刚生成的凭据。
4. 为滑块、文字图片、刷新入口增加键盘及 ARIA 支持；文字图片在键盘操作时显示十字定位符。卸载时移除事件、清理延时任务，忽略过期响应，防止重复校验请求；点选完成后立即锁定，取消时不再发送延迟校验。
5. 明确 Vue 文件扩展名并补充 TypeScript 声明。小屏幕保持官方宽高比例，后台仍按 310 像素坐标校验。
6. 按用户要求复用模板的 `btn-soft-primary`、`btn-light btn-icon`、圆角边框及状态色。移除与这些类冲突的少量官方固定白底、阴影和悬停颜色；保留组件定位和尺寸计算。刷新改为原生按钮，图标使用模板本地图标库。文字点选和滑块跟随明暗主题，外层使用现有紧凑弹窗，不增加业务 CSS。
7. 滑块使用统一的 0–263 原图位移，鼠标、触屏与键盘均限制在此范围。按钮与拼块按各自宽度映射行程，拼块在图片容器内定位并裁切；失败提示期间锁定拖动，刷新清理旧定时器并复位，触控取消不提交校验。
8. 滑块与点选的结果提示使用主题淡绿／淡红底色，背景不透明度为 85%；文字、图标与滑块按钮保持完全不透明。背景色跟随明暗主题，不支持色彩混合的浏览器回退到实色。

每次打开弹窗随机选择 `blockPuzzle` 或 `clickWord`，同次弹窗刷新保持类型。模拟后端根据官方素材裁切拼图，或叠加汉字生成文字点选 PNG，保存类型、答案、token、过期时间和核验结果，不部署官方 Java 后端。文字图片使用项目已有 Noto Sans CJK 字体及服务端 `@napi-rs/canvas` 渲染。组件升级时应重新核对补丁、资源摘要和登录回归测试。
