<template>
  <el-drawer :model-value="modelValue" title="样品详情" size="760px" @close="$emit('update:modelValue', false)">
    <el-tabs model-value="entrust">
      <el-tab-pane label="委托信息" name="entrust" />
      <el-tab-pane label="样品信息" name="sample" />
      <el-tab-pane label="试验信息" name="test" />
      <el-tab-pane label="原始记录" name="record" />
      <el-tab-pane label="报告预览" name="report" />
      <el-tab-pane label="修改记录" name="change" />
      <el-tab-pane label="问题记录" name="issue" />
    </el-tabs>
    <el-form label-position="top" >
      <el-row :gutter="12">
        <el-col :span="12"><el-form-item label="委托编号"><el-input model-value="WT-202512-0031" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="样品编号"><el-input model-value="HN-S-202512-001" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="报告编号"><el-input model-value="BG-202512-0148" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="检测项目"><el-input model-value="混凝土抗压" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="外部ERP合同编号"><el-input model-value="KD-2025-1188" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="采集状态"><el-select model-value="已同步"><el-option label="已同步" value="已同步" /></el-select></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="模板格式"><el-input model-value="REPORT_DEFAULT" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="报告展现方式"><el-input model-value="Word 模板" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="原始记录"><el-input type="textarea" model-value="自动采集数据已同步 6 条；人工录入 2 条；待主检确认。" /></el-form-item></el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button>保存</el-button>
      <el-button type="primary">保存并完成检测</el-button>
      <el-button>重新生成 Word</el-button>
      <el-button>发送邮件</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>
