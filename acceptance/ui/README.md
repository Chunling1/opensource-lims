# 页面测试

先构建前端，再在独立的临时实例中运行 upgrade、seed-demo 和 serve（默认测试端口 8899）。不要连接生产库。p10 与 shots 会修改演示数据，两者应分别使用全新数据库。

本目录执行 `npm ci` 安装 Playwright。当前脚本使用 Microsoft Edge（msedge channel），运行机器需要安装 Edge。

```sh
node p10.ui.mjs http://127.0.0.1:8899/
node shots.mjs http://127.0.0.1:8899/
```

结果截图默认在本目录 artifacts 下，不进入版本库。截图生成不代表完成视觉核验。

后端独立测试在仓库根目录执行：

```sh
python -m unittest discover -s acceptance -t .
python -m unittest discover -s tests
```

PostgreSQL 测试可通过 LIMS_TEST_POSTGRES 指向独立测试数据库。测试会创建和清理自己的 schema，禁止使用生产连接。
