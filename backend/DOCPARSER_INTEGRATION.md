# DocParser 原包深度接入说明

发布标识：`DOCPARSER-DEEP-INTEGRATION-20260901-v3`

## 不变量

- `app/docparser_original/` 保存用户提供压缩包中的源码、模板和素材，运行前按 `app/docparser_source_manifest.json` 逐文件校验 SHA-256。
- 原包的 `entrust_maker.py`、`report_maker.py`、`template_helper.py` 等生产代码不修改。
- 字段替换在独立子进程中调用原包类；完成后重建 DOCX 包，仅允许字段 XML、字段产生的图片关系、图片资源和 `updateFields` 设置变化。
- 非字段段落、图形、表格几何、分节、页码域、原有关系或包成员发生变化时，生成失败。

## 模板选择

委托单：

- 工程模式：`LAB-4204g-202601_tpl.docx`。
- 产品、送样、抽样、检验、校准模式：`LAB-4204d-202601_tpl.docx`。
- 显式业务模式、打印请求与推断结果冲突时拒绝生成。

报告：

- 报告类型映射为产品、抽样、工程、检验、校准五类。
- 产品/抽样支持 `1p` 与 `2p` 首页；其余类型只支持 `1p`。
- 中心由持久化报告编号前缀确定，并与显式出具中心、出具部门关键词结果交叉核对。
- 编号前缀、出具中心或部门规则不一致时拒绝生成，不回退到其他中心。
- CMA、CNAS、印章和报告格式作为选择证据写入模板快照；要求标志但缺少有效机构配置时拒绝生成。

默认部门关键词规则可通过 `DOCPARSER_DEPARTMENT_RULES` 覆盖。配置为 JSON 数组，每项只允许：

```json
[
  {"center": "NCSA", "keywords": ["空调", "通风"]}
]
```

## 启用与回滚

默认使用历史引擎。候选发布必须同时配置：

```text
DOCUMENT_TEMPLATE_ENGINE=docparser-original-v3
DOCPARSER_ROLLOUT_STARTED_AT=<ISO-8601 发布时刻>
```

只有创建时间不早于发布时刻的委托和报告使用新引擎，历史文件保持原版式。回滚只需恢复前一不可变发布目录或把 `DOCUMENT_TEMPLATE_ENGINE` 改回 `legacy`；不需要数据库迁移。

机构英文名、联系方式、CMA/CNAS 编号、二维码地址等由 `DOCPARSER_INSTITUTION_PROFILES` 服务器配置提供，不在源码中写入演示证书或外部地址。

## 报告正文工作流

原报告模板正文位置是“补充内容编写说明”，不是结构化结果占位符，因此系统不会猜测或重写正文。流程为：

1. 系统按规则选择模板并替换固定字段；
2. 用户下载 `/api/reports/<report_no>/continuation-template`；
3. 删除说明、填写正文后按“报告后续页”上传；
4. 服务端核验报告编号、注意事项页、外部资源、说明已删除和文件类型；
5. 正式 PDF 只保留服务器生成的封面/首页/注意事项，并插入上传正文；
6. 未上传完成正文或正文仍含说明时，正式生成与签发失败。

## 依赖

原包新增的纯 Python 依赖随候选发布放在 `_vendor/`，仅由隔离 worker 的 `PYTHONPATH` 使用；不会修改或污染生产共享虚拟环境。
