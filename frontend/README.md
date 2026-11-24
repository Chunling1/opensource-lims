# Open-LIMS Frontend (Vue 3 + TypeScript + Tabler)

基于 Vue 3、TypeScript、Pinia、Vue Router 与开源 Tabler (MIT) 构建的实验室信息管理系统（LIMS）前端。

## 快速开始

```bash
npm install
npm run dev
```

默认开发服务器地址：`http://127.0.0.1:5189`，`/api` 请求自动代理至后端 `http://127.0.0.1:5100`（可通过环境变量 `PLATFORM_BACKEND_URL` 覆盖）。

## 常用命令

- `npm run build`：执行模板合规检查、组件适配检查、TypeScript 类型检查与生产构建
- `npm run test:platform`：运行核心平台单元测试
- `npm run verify:template`：验证模板与图标规范（纯 Tabler + Tabler Icons）
