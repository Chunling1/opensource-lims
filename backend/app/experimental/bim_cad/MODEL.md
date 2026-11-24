# BIM/CAD 实验模型部署说明

该目录不保存约 93MB 的 ONNX 模型。部署时将受控模型放入持久化模型目录，并通过
`BIM_CAD_MODEL_PATH` 注入绝对路径。建议生产路径：

`/opt/lims/data/models/bim-cad/M2_DA_best.onnx`

- 模型文件：`M2_DA_best.onnx`
- SHA256：`d54e1ed1644bf795ba3dbdbfef5355b55e9f0110002f79de1bf2c6c2abdf6077`
- 输入：`1 × 3 × 512 × 512`
- 输出类别：背景、墙体、窗、门
- 研究样本 mIoU：`0.787`（仅作为研究基准，不代表任意上传图纸准确率）

模型校验不通过、依赖缺失或功能开关关闭时，服务必须拒绝识别，不得静默切换到演示结果。


