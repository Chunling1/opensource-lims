<template>
  <component
    :is="pageView ? SampleFormSurface : ElDialog"
    :embedded="!!embeddedSection"
    :return-label="mode === 'entrust' ? '返回委托登记' : '返回样品登记'"
    :form-label="mode === 'entrust' ? '委托信息表单' : '样品信息表单'"
    :model-value="modelValue"
    width="980px"
    top="5vh"
     data-ui="entrust-dialog"
    :close-on-click-modal="false"
    :before-close="handleDialogBeforeClose"
  >
    <template #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <span>{{ dialogTitle }}</span>
        <button v-if="session.canCorrectBusinessData && (effectiveReportNo || activeEntrustId)" type="button"
          class="btn btn-sm" :class="administratorEditing ? 'btn-primary' : 'btn-outline-primary'"
          :disabled="submitting || sampleFormLoading || Boolean(sampleFormError) || session.businessReadOnly"
          :aria-pressed="administratorEditing" @click="toggleAdministratorEditing">
          <i class="ti ti-edit me-1" aria-hidden="true"></i>{{ administratorEditing ? '退出管理员编辑' : '管理员编辑' }}
        </button>
        <el-tag
          v-if="mode === 'entrust'"
          size="small"
          :type="entrustCompleted ? 'success' : 'warning'"
          
        >{{ entrustStatusLabel }}</el-tag>
      </div>
    </template>
    <div v-if="embeddedSection && session.canCorrectBusinessData && (effectiveReportNo || activeEntrustId)" class="d-flex justify-content-end mb-3">
      <button type="button" class="btn btn-sm btn-outline-primary"
        :disabled="submitting || sampleFormLoading || Boolean(sampleFormError) || session.businessReadOnly"
        :aria-pressed="administratorEditing" @click="toggleAdministratorEditing">{{ administratorEditing ? '退出管理员编辑' : '管理员编辑' }}</button>
    </div>
    <div v-if="!readOnly && session.aiVoiceEnabled && session.canAction('ai.voice.use')" >
      <AiVoiceDraft
        :schema-id="mode === 'entrust' ? 'entrust.v1' : 'sample.v1'"
        :current-values="mode === 'entrust' ? f : s"
        @apply="applyVoiceDraft"
      />
      <span>AI 只生成候选差异，不会自动保存或完成流程。</span>
    </div>
    <el-alert v-if="sampleFormLoading || sampleFormError" :type="sampleFormError ? 'error' : 'info'" :closable="false" :title="sampleFormError || '正在加载已保存样品及标准参数，请稍候…'" />
    <div v-if="administratorEditing" class="alert alert-warning" role="status">管理员编辑中：修改仅保存到当前记录。保存前需填写修改说明，系统记录修改前后内容。</div>
    <el-alert v-if="legacyMigrationHold" title="迁移待复核：已保留原委托、样品和编号；请核对项目、参数、模板后再启用流转。附件本次未迁入。" type="warning" :closable="false" />
    <el-button v-if="sampleFormError && !effectiveReportNo && s.baseReportNo" :disabled="sampleFormLoading" @click="selectSourceReport({ reportNo: s.baseReportNo, sampleNo: '' })">重新读取原报告</el-button>
    <fieldset :inert="legacyMigrationHold || undefined" :disabled="readOnly || legacyMigrationHold || sampleFormLoading || Boolean(sampleFormError)" class="border-0 p-0 m-0">
    <!-- ============ 新增委托 ============ -->
    <div v-if="mode === 'entrust'" class="card"><div class="card-body">
      <div class="mb-4"><el-button size="small" type="primary" plain @click="openCopyDialog">已有表单复制</el-button></div>
      <el-alert
        v-if="entrustErrorList.length"
        type="error"
        :closable="false"
        show-icon
        
        :title="`请完成 ${entrustErrorList.length} 个必填项：${entrustErrorList.join('、')}`"
      />
      <el-alert
        v-if="draftSavedAt"
        type="info"
        :closable="false"
        show-icon
        
        :title="`已恢复 ${draftSavedAt} 保存的委托草稿`"
      />
      <div class="row g-3 mb-3">
        <div class="row g-3 m-0 p-0">
          <div data-field="projectName" class="col-12" :class="{ 'text-danger': entrustErrors.projectName }"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">项目名称</label><div class="col"><el-input v-model="f.projectName" aria-label="项目名称" placeholder="例如：办公楼围护结构检测" /><small v-if="entrustErrors.projectName" class="text-danger small d-block mt-1">{{ entrustErrors.projectName }}</small></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托编号</label><div class="col"><el-input v-model="f.entrustNo" :disabled="!administratorEditing || !activeEntrustId" placeholder="系统按登记顺序自动生成" /></div></div></div>
          <div data-field="entrustDate" class="col-12 col-lg-4" :class="{ 'text-danger': entrustErrors.entrustDate }"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托日期</label><div class="col"><WorkflowDatePicker v-model="f.entrustDate" :disabled="!administratorEditing" aria-label="委托日期" placeholder="系统自动生成" /><small v-if="entrustErrors.entrustDate" class="text-danger small d-block mt-1">{{ entrustErrors.entrustDate }}</small></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托人</label><div class="col"><el-input v-model="f.consignor" aria-label="委托人" placeholder="填写委托联系人姓名" /></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托人电话</label><div class="col"><el-input v-model="f.consignorPhone" aria-label="委托人电话" placeholder="例如：13800000000" /></div></div></div>
        </div>
      </div>

      <div class="row g-3 mb-3">
        <div class="row g-3 m-0 p-0">
          <div class="col-12 col-lg-6"><label class="form-label d-block">合同甲方</label>
            <CustomerPicker v-model="f.contractPartyA" label="合同甲方" :allow-manual="selectedContractType === '不回传外部ERP合同'" :disabled="readOnly || !modelValue || contractPartyALocked" />
          </div>
          <div class="col-12 col-lg-6"><label class="form-label d-block">其他甲方（付款方）</label>
            <CustomerPicker v-model="f.otherPartyA" label="其他甲方（付款方）" :allow-manual="selectedContractType === '不回传外部ERP合同'" :disabled="readOnly || !modelValue" />
          </div>
          <div data-field="client" class="col-12 col-lg-6" :class="{ 'text-danger': entrustErrors.client }"><label class="form-label d-block">委托单位</label>
            <CustomerPicker v-model="f.client" label="委托单位" multiple allow-manual :disabled="readOnly || !modelValue" @picked="onPickClient" />
            <small v-if="entrustErrors.client" class="text-danger small d-block mt-1">{{ entrustErrors.client }}</small>
          </div>
          <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托单位地址</label><div class="col"><el-input v-model="f.clientAddr" placeholder="手动填写" /></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托单位法人</label><div class="col"><el-input v-model="f.clientLegal" placeholder="手动填写" /></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托单位电话</label><div class="col"><el-input v-model="f.clientPhone" placeholder="手动填写" /></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托单位邮编</label><div class="col"><el-input v-model="f.clientZip" placeholder="手动填写" /></div></div></div>
        </div>
      </div>

      <div class="row g-3 mb-3">
        <div class="row g-3 m-0 p-0">
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">工程备案编号</label><div class="col"><el-input v-model="f.projectRecordNo" placeholder="手动填写" /></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">工程编码(交易中心)</label><div class="col"><el-input v-model="f.projectTradeCode" placeholder="手动填写" /></div></div></div>
          <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">工程地址</label><div class="col"><el-input v-model="f.projectAddr" placeholder="手动填写" /></div></div></div>
        </div>
      </div>

      <div class="row g-3 mb-3">
        <div class="row g-3 m-0 p-0">
          <div data-field="handleDept" class="col-12" :class="{ 'text-danger': entrustErrors.handleDept }"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">经办部门</label><div class="col">
            <el-select v-model="f.handleDept" aria-label="经办部门" placeholder="请选择实际经办部门" >
              <el-option v-for="d in handleDepts" :key="d.id" :label="d.fullName" :value="d.name" />
            </el-select>
            <small v-if="entrustErrors.handleDept" class="text-danger small d-block mt-1">{{ entrustErrors.handleDept }}</small>
          </div></div></div>
          <div data-field="handler" class="col-12 col-lg-4" :class="{ 'text-danger': entrustErrors.handler }"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">经办人</label><div class="col"><el-input v-model="f.handler" aria-label="经办人" placeholder="填写实际经办人姓名" /><small v-if="entrustErrors.handler" class="text-danger small d-block mt-1">{{ entrustErrors.handler }}</small></div></div></div>
          <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">经办人联系电话</label><div class="col"><el-input v-model="f.handlerPhone" aria-label="经办人联系电话" placeholder="例如：010-00000000" /></div></div></div>
        </div>
      </div>
    </div></div>

    <!-- ============ 添加样品 ============ -->
    <div v-else >
      <div v-if="!readOnly" class="d-flex flex-wrap align-items-center gap-2 mb-3" data-ui="sample-progress-row">
        <el-button size="small" type="primary" plain @click="openCopyDialog">已有表单复制</el-button>
      </div>
      <el-form label-width="96px">
        <template v-if="embeddedSection !== 'sample'">
        <details v-if="!embeddedSection" class="card" open><summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">关联委托</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
        <el-form-item v-if="!isChange" label="委托单"  required>
          <EntrustSelection v-model="sampleEntrustNo" :options="entrustOptions" :disabled="!!activeSavedReportNo || derivedSchemeLocked || sampleFormLoading" @change="onSampleEntrustChange" />
        </el-form-item>
        </div></details>
        <details v-if="sampleEntrustNo" class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">该样品的委托信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">原委托编号</label><div class="col"><el-input v-model="sampleEntrust.entrustNo" disabled /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托日期</label><div class="col"><WorkflowDatePicker v-model="sampleEntrust.entrustDate" disabled placeholder="由原委托单带入（只读）" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">项目类型</label><div class="col"><el-input v-model="sampleEntrust.projectType" disabled /></div></div></div>
            <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">项目名称</label><div class="col"><el-input v-model="sampleEntrust.projectName" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托人</label><div class="col"><el-input v-model="sampleEntrust.consignor" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托人电话</label><div class="col"><el-input v-model="sampleEntrust.consignorPhone" /></div></div></div>
          </div>
        </div></details>
        <details v-if="sampleEntrustNo" class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">委托单位信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12"><label class="form-label d-block">合同甲方</label><CustomerPicker v-model="sampleEntrust.contractPartyA" label="样品合同甲方" :allow-manual="sampleContractType === '不回传外部ERP合同'" :disabled="readOnly || !modelValue || sampleContractPartyALocked" /></div>
            <div class="col-12"><label class="form-label d-block">其他甲方（付款方）</label><CustomerPicker v-model="sampleEntrust.otherPartyA" label="样品其他甲方（付款方）" :allow-manual="sampleContractType === '不回传外部ERP合同'" :disabled="readOnly || !modelValue" /></div>
            <div class="col-12"><label class="form-label d-block">委托单位</label><CustomerPicker v-model="sampleEntrust.client" label="样品委托单位" multiple allow-manual :disabled="readOnly || !modelValue" @picked="onPickSampleClient" /></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">单位地址</label><div class="col"><el-input v-model="sampleEntrust.clientAddr" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">法人</label><div class="col"><el-input v-model="sampleEntrust.clientLegal" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">单位电话</label><div class="col"><el-input v-model="sampleEntrust.clientPhone" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">邮编</label><div class="col"><el-input v-model="sampleEntrust.clientZip" /></div></div></div>
          </div>
        </div></details>
        <details v-if="sampleEntrustNo" class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">工程基本属性</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">工程备案编号</label><div class="col"><el-input v-model="sampleEntrust.projectRecordNo" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">交易中心工程编号</label><div class="col"><el-input v-model="sampleEntrust.projectTradeCode" /></div></div></div>
            <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">工程地址</label><div class="col"><el-input v-model="sampleEntrust.projectAddr" /></div></div></div>
          </div>
        </div></details>
        <details v-if="sampleEntrustNo" class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">业务办理信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品登记部门</label><RegistrarPicker kind="departments" :value="sampleEntrust.handleDept" :disabled="!administratorEditing || readOnly" @picked="selectRegistrarDepartment" /></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品登记人</label><RegistrarPicker kind="people" :value="sampleEntrust.handler" :disabled="!administratorEditing || readOnly" @picked="selectRegistrarPerson" /></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">经办人电话</label><div class="col"><el-input v-model="sampleEntrust.handlerPhone" /></div></div></div>
          </div>
        </div></details>
        <details v-if="sampleEntrustNo" class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">财务相关信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">发票类型</label><div class="col"><el-input v-model="sampleEntrust.invoiceType" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">纳税人识别号</label><div class="col"><el-input v-model="sampleEntrust.taxNo" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">开票单位名称</label><div class="col"><el-input v-model="sampleEntrust.companyName" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">开票地址</label><div class="col"><el-input v-model="sampleEntrust.bizAddr" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">开户银行</label><div class="col"><el-input v-model="sampleEntrust.bank" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">银行账号</label><div class="col"><el-input v-model="sampleEntrust.account" /></div></div></div>
          </div>
        </div></details>
        </template>
        <template v-if="embeddedSection !== 'commission'">
        <details class="card" open><summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">检测方案</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
        <el-form-item label="检测方案"  required>
          <div class="input-group">
            <el-input :model-value="schemeDisplay" readonly placeholder="点「选择」按部门选检测方案（显示编号和名称）"  />
            <el-button :disabled="schemeLocked" @click="openSchemeDialog">选择</el-button>
          </div>
          <div v-if="schemeLocked" >{{ derivedSchemeLocked ? '已继承原报告，检测方案及对应部门不可更改' : '样品号/报告号已生成，检测方案及编号类别已锁定，后续更改不能重新选择' }}</div>
          <div v-if="schemeMappingText" >{{ schemeMappingText }}</div>
        </el-form-item>
        <el-alert v-if="sampleConfigErrors.length" type="error" :closable="false" show-icon  :title="sampleConfigErrors.join('；')" />
        </div></details>
        <details class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">送样信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品编号</label><div class="col"><el-input v-if="administratorEditing && effectiveReportNo" v-model="s.sampleNo" /><el-input v-else :model-value="sampleAutoNo" disabled placeholder="选择检测方案后显示编号代码" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品/工程名称</label><div class="col"><el-input v-model="s.sampleName" placeholder="手填（样品名称 / 工程名称）" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label for="curtain-engineering-name" class="form-label mb-1">工程名称（幕墙）</label><div class="col"><el-input id="curtain-engineering-name" v-model="s.engineeringName" placeholder="填写幕墙报告中的工程名称（选填）" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">规格型号</label><div class="col"><el-input v-model="s.spec" placeholder="手填" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">生产厂家</label><div class="col"><el-input v-model="s.manufacturer" placeholder="手填" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">检测部门/检测室</label><div class="col">
              <el-select v-model="s.testDept" disabled aria-label="检测部门/检测室" placeholder="选择方案后自动带入" popper-class="sample-organization-select-popper">
                <template #label="{ value }">
                  <span  :title="organizationDisplayName(value)" :aria-label="organizationDisplayName(value)">{{ organizationDisplayName(value) }}</span>
                </template>
                <el-option v-for="o in sampleDepartmentOptions" :key="o" :label="organizationDisplayName(o)" :value="o">
                  <span  :title="organizationDisplayName(o)">{{ organizationDisplayName(o) }}</span>
                </el-option>
              </el-select>
            </div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">是否加急</label><div class="col"><el-select v-model="s.urgent"><el-option label="否" value="否" /><el-option label="是" value="是" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">检测期限</label><div class="col"><el-input v-model="s.deadline" placeholder="正常/加急" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">外观</label><div class="col"><el-select v-model="s.appearance" filterable allow-create default-first-option clearable placeholder="与封样状态同步"><el-option v-for="o in SAMPLE_OPTS.appearance" :key="o" :label="o" :value="o" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">铭牌</label><div class="col"><el-select v-model="s.nameplate" clearable placeholder="有/无"><el-option v-for="o in SAMPLE_OPTS.nameplate" :key="o" :label="o" :value="o" /></el-select></div></div></div>
          </div>
          <div class="row g-3 mt-0">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品数量（含单位）</label><div class="col"><el-input :model-value="sampleQuantityText(s.sampleAmount,s.unit)" @update:model-value="setSampleQuantity(s,$event)" placeholder="如：3台、2台及3套" /></div></div></div>
            <div class="col-12 col-lg-4"><label class="form-label d-block">商标</label>
              <div >
                <el-input v-model="s.trademark" placeholder="商标文字（可留空只放图样）"  />
                <el-upload :disabled="sampleImageBlocked" :show-file-list="false" accept="image/png,image/jpeg" :auto-upload="false" :on-change="onTrademarkPick">
                  <el-button size="small" :disabled="sampleImageBlocked">{{ s.trademarkImage ? '更换图样' : '上传图样' }}</el-button>
                </el-upload>
                <el-image v-if="s.trademarkImage" :src="s.trademarkImage" :preview-src-list="[s.trademarkImage]" preview-teleported hide-on-click-modal fit="contain" alt="商标图片" title="点击查看大图" class="img-thumbnail avatar-lg" />
                <el-button v-if="s.trademarkImage" :disabled="sampleImageBlocked" size="small" text type="danger" @click="s.trademarkImage = ''">清除</el-button>
                <span v-if="sampleImageLoading" role="status">商标图样加载中，文字资料可先查看；图样就绪后可保存、预览和导出。</span>
                <span v-if="sampleImageError" role="alert">{{ sampleImageError }}<el-button size="small" @click="loadSavedSampleImage">重试图样</el-button></span>
              </div>
            </div>
          </div>
          <div class="row g-3 mt-0">
            <div class="col-12 col-md-6 col-lg-3"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">出厂编号</label><div class="col"><el-input v-model="s.factoryNo" placeholder="手填" /></div></div></div>
            <div class="col-12"><label class="form-label mb-2">生产日期</label><ProductionDatesEditor v-model="s.produceDate" v-model:rows="s.productionDates" :disabled="readOnly" :language="s.reportLanguage" :limits="{ sampleTime: s.sampleTime, sendDate: s.sendDate, entrustDate: selectedEntrustDate }" /></div>
            <div class="col-12 col-md-6 col-lg-3"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">送样日期</label><div class="col"><WorkflowDatePicker v-model="s.sendDate" strict-order :previous-date="dateBoundary([s.produceDate, s.sampleTime], 'max')" placeholder="可早于或晚于委托日期" /></div></div></div>
            <div class="col-12 col-md-6 col-lg-3"><label class="form-label d-block">是否现场检测</label><el-switch v-model="s.isOnsiteTesting" :disabled="readOnly" @change="onOnsiteTestingChange" /></div>
          </div>
        </div></details>
        <details class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">检测与报告配置</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-md-6 col-xl-3"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告标题</label><div class="col"><el-select v-model="s.centerPrefix" :disabled="readOnly" @change="s.seal = sealByCenter($event)" placeholder="决定报告编号前缀与报告标题"><el-option v-for="c in centers" :key="c.prefix" :label="`${c.name}（${c.prefix}）`" :value="c.prefix" /></el-select></div></div></div>
            <div class="col-12 col-md-6 col-xl-3"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告格式</label><div class="col"><el-select v-model="s.reportType" :disabled="!s.centerPrefix" placeholder="先选报告标题"><el-option v-for="rt in centerTypes" :key="rt" :label="rt" :value="rt" /></el-select></div></div></div>
            <div class="col-12 col-md-6 col-xl-3"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告语言</label><div class="col"><el-select :model-value="s.reportCategory === '英文' ? 'EN' : s.reportLanguage" :disabled="readOnly || !s.centerPrefix || s.reportType.includes('校准') || s.reportCategory === '英文'" @change="s.reportLanguage = $event"><el-option label="中文" value="CN" /><el-option label="英文" value="EN" /></el-select></div></div></div>
            <div class="col-12 col-md-6 col-xl-3"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">封面首页版式</label><div class="col"><el-select v-model="s.reportTemplateVariant" :disabled="readOnly || !s.centerPrefix"><el-option label="标准版" value="Standard" /><el-option v-if="['产品报告', '抽样报告'].includes(s.reportType)" label="扩展版（长首页／两页）" value="Extended" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><label for="sample-test-category" class="form-label">检测类别</label>
              <el-select id="sample-test-category" v-model="s.testCategory" :disabled="readOnly" aria-label="检测类别">
                <el-option v-if="s.testCategory && !sampleTestCategories.includes(s.testCategory)" :label="s.testCategory" :value="s.testCategory" disabled />
                <el-option v-for="category in sampleTestCategories" :key="category" :label="category" :value="category" />
              </el-select>
            </div>
            <div class="col-12"><div class="row g-3">
              <section class="col-12" aria-label="检测依据">
                <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                  <h6 class="mb-0">检测依据 <span class="text-muted">（{{ commissionBasisRecords.length }} 项）</span></h6>
                  <el-button type="primary" plain :disabled="readOnly" @click="openBasisDialog"><i class="ti ti-search me-1" aria-hidden="true"></i>选择检测依据</el-button>
                </div>
                <div class="row g-3">
                  <div class="col-12 col-xl-7"><StandardTitleChoices id="commission-standard" v-model="s.basisTitleStyles" :codes="commissionBasisRecords.map(row => row.key)" :names="Object.fromEntries(commissionBasisRecords.map(row => [row.key, row.name]))" :labels="Object.fromEntries(commissionBasisRecords.map(row => [row.key, row.code]))" default-style="none" :readonly="readOnly" /></div>
                  <div class="col-12 col-xl-5"><CommissionTextPreview id="commission-basis-text" label="检测依据模板文字" :text="commissionBasisText"
                    v-model:separator="s.basisSeparator" :readonly="readOnly" placeholder="选择检测依据后，按委托单文字格式显示。" /></div>
                </div>
              </section>
              <section class="col-12" aria-label="能力项目/参数">
                <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                  <h6 class="mb-0">检测项目 / 参数 <span class="text-muted">（{{ selectedTestItemRows.length }} 项）</span></h6>
                  <el-button type="primary" plain :disabled="readOnly" @click="openCapabilityDialog"><i class="ti ti-list-check me-1" aria-hidden="true"></i>选择检测项目</el-button>
                </div>
                <CommissionTextPreview id="commission-items-text" label="检测项目模板文字" :text="commissionItemsText"
                  v-model:separator="s.itemsSeparator" :readonly="readOnly" placeholder="选择库内项目或添加库外参数后，按委托单文字格式显示。" />
              </section>
            </div>
            </div>
            <el-alert v-if="capabilityUnavailable" type="warning" :closable="false" show-icon class="col-12"
              title="该标准暂未匹配到已启用的能力项目"
              description="可在“选择检测项目”中添加库外参数。库外参数不影响流程流转；CMA/CNAS 授权按所选标准核对。" />
            <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">检测地点</label><div class="col">
              <el-input v-if="s.isOnsiteTesting" v-model="s.onsiteTestLocation" :disabled="readOnly" placeholder="请输入实际现场检测完整地址，可与标准认可场所不同" @input="syncParameterLocations" />
              <el-input v-else :model-value="s.testLocation" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" readonly placeholder="选择检测参数后自动汇总完整地址，多个地点全部列出" />
            </div></div></div>
            <div v-if="unavailableCapabilityIds.length" class="col-12" role="alert">
              <div class="alert alert-warning mb-0">
                <strong>历史参数当前不可用</strong>
                <p class="mb-2">{{ unavailableCapabilityLabels.join('、') }}。原参数、顺序和地点已保留；可保存草稿，完成登记前请移除或重新选择。</p>
                <button v-if="!readOnly" type="button" class="btn btn-sm btn-outline-primary" @click="openCapabilityDialog">处理不可用参数</button>
              </div>
            </div>
            <p v-if="parameterLocationError" class="col-12 text-danger small mb-0" role="alert">{{ parameterLocationError }}；请打开“选择检测项目”补齐地点。</p>
            <div class="col-12"><label class="form-label d-block">判定标准</label>
              <JudgmentBasisInput :key="`${props.modelValue}:${props.changeReportNo || ''}`" ref="judgmentInput"
                :model-value="s.judgmentEntries" :legacy="s.standardJudge" :disabled="readOnly" @update:model-value="setJudgmentEntries" />
              <JudgmentStandardDisplay class="mt-3" id="commission-judgment" :source="s.judgmentEntries ?? s.standardJudge" :records="commissionBasisRecords" :settings="s.judgmentDisplay" :language="s.reportLanguage" :readonly="readOnly" />
            </div>
            <div v-if="s.manualCapabilityItems.length" class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">库外使用说明（选填）</label><div class="col">
              <el-input v-model="s.manualCapabilityReason" type="textarea" :rows="2"
                placeholder="可填写补充说明；留空不影响流程流转" />
            </div></div></div>
            <div v-if="s.manualCapabilityItems.length && !s.isOnsiteTesting" class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">库外检测地点</label><div class="col">
              <p class="mb-0 text-body small">在“选择检测项目”中为每个库外参数选择与库内一致或单独地点。</p>
            </div></div></div>
            <el-alert v-if="cmaScopeWarn" type="warning" :closable="false" show-icon class="col-12"
              title="盖章含 CMA，但检测依据不在「一单一库」范围内，请核实（合同评审及后续阶段会持续提示）" />
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">盖章要求</label><div class="col"><el-select v-if="['NCSA', 'NCAS'].includes(s.centerPrefix)" v-model="s.seal" :disabled="readOnly"><el-option label="不加 CMA（保留 CNAS）" value="CNAS" /><el-option label="加 CMA + CNAS" value="CMA + CNAS" /></el-select><el-input v-else :model-value="s.seal" disabled placeholder="由检测中心决定" /></div></div></div>
            <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告编号</label><div class="col"><el-input v-if="administratorEditing && effectiveReportNo" :model-value="sampleReportNo" @update:model-value="correctedReportNo = $event" /><el-input v-else :model-value="sampleReportNo" disabled placeholder="选择报告标题和检测方案后显示编号代码" /></div></div></div>
            <div v-if="!isChange" class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告类别</label><div class="col">
              <el-select v-model="s.reportCategory" :disabled="!!effectiveReportNo || sampleFormLoading">
                <el-option label="普通委托" value="普通" /><el-option label="补充报告(原号+BC)" value="补充" />
                <el-option label="英文报告(原号+(E))" value="英文" /><el-option label="分项报告(原号+-后缀)" value="分项" />
              </el-select>
            </div></div></div>
            <div v-if="s.reportCategory !== '普通'" class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">原报告(继承委托+样品信息)</label><div class="col">
              <SourceReportSelect v-model="s.baseReportNo" @selected="selectSourceReport" :category="s.reportCategory" :disabled="readOnly || submitting || !!effectiveReportNo" />
            </div></div></div>
            <div v-if="s.reportCategory === '分项'" class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">分项后缀</label><div class="col"><el-input v-model="s.subSuffix" placeholder="如 1 / 主体结构" /></div></div></div>
          </div>
        </div></details>

        <details class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">项目信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">委托单备注</label><div class="col"><el-input v-model="s.remark" type="textarea" :rows="2" placeholder="出现在委托单上" /></div></div></div>
            <div class="col-12"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告首页备注</label><div class="col"><el-input v-model="s.homepageRemark" type="textarea" :rows="2" placeholder="出现在报告首页（与委托单备注独立）" /></div></div></div>
          </div>
        </div></details>

        <details v-if="isSamplingBusiness" class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">抽样信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">抽样单位</label><div class="col"><el-input v-model="s.sampleUnit" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">抽样人</label><div class="col"><el-input v-model="s.sampler" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">抽样时间</label><div class="col"><WorkflowDatePicker v-model="s.sampleTime" strict-order :previous-date="productionDateBoundary(s.produceDate)" :next-date="s.sendDate" placeholder="不早于生产，不晚于送样" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">抽样数量</label><div class="col"><el-input v-model="s.sampleQty" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">基数</label><div class="col"><el-input v-model="s.entrustQty" placeholder="原「委数」" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">受检单位</label><div class="col"><el-input v-model="s.inspectedUnit" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">任务来源</label><div class="col"><TemplateEditableSelect id="sample-task-source" v-model="s.taskSource" label="任务来源" :options="SAMPLE_OPTS.taskSource" :readonly="readOnly || legacyMigrationHold || submitting || sampleFormLoading || Boolean(sampleFormError)" placeholder="选择或直接输入任务来源" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">抽样地点</label><div class="col"><el-input v-model="s.samplingLocation" placeholder="手填" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品/抽样单编号</label><div class="col"><el-input :model-value="sampleAutoNo" disabled placeholder="同样品编号" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品到达日期</label><div class="col"><input id="sample-arrival-date" class="form-control" :value="s.sampleArrivalDate" aria-label="样品到达日期" readonly placeholder="随送样日期同步" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品等级</label><div class="col"><el-input v-model="s.sampleGrade" placeholder="手填" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">封样状态</label><div class="col"><el-input v-model="s.sealStatus" placeholder="手填" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">检查封样人员</label><div class="col"><el-input v-model="s.sealChecker" placeholder="手填" /></div></div></div>
          </div>
        </div></details>

        <el-collapse v-model="advancedSections" >
          <el-collapse-item name="business" title="更多业务信息（结算、子项目、报告交付）">
        <details class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">结算信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">标准价格</label><div class="col"><el-input v-model="s.stdPrice" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">缴费情况</label><div class="col"><el-select v-model="s.payStatus" filterable allow-create default-first-option clearable placeholder="选择/输入"><el-option v-for="o in SAMPLE_OPTS.payStatus" :key="o" :label="o" :value="o" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><div class="d-flex flex-wrap justify-content-between gap-1"><label class="form-label mb-1">支付方式</label><small class="text-muted">为空默认银行转账</small></div><div class="col"><el-input v-model="s.payWay" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">已缴费</label><div class="col"><el-input v-model="s.paid" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">其他</label><div class="col"><el-input v-model="s.otherSettle" /></div></div></div>
          </div>
        </div></details>

        <details class="card" open><summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">子项目信息</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <SampleSubprojectEditor v-model="s.subItems" :entrust-no="sampleEntrustNo" :contract-no="sampleEntrust.contractNo" :report-no="effectiveReportNo" :internal-contract="sampleContractType === '不回传外部ERP合同'" :disabled="readOnly || sampleFormLoading || Boolean(sampleFormError)" :departments="organizationDepartments.map(department => department.fullName || department.name)" />
        </div></details>

        <details class="card" open>
          <summary class="card-header d-flex align-items-center justify-content-between gap-2"><h5 class="card-title mb-0">报告发送</h5><span class="text-muted small">展开 / 收起</span></summary><div class="card-body">
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告承诺时间(外部)</label><div class="col"><WorkflowDatePicker v-model="s.sendOutTime" :previous-date="sampleFlowBaseDate" require-previous placeholder="选择日期" missing-previous-reason="请先填写送样日期或补全委托日期。" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告承诺时间(内部)</label><div class="col"><WorkflowDatePicker v-model="s.sendInTime" :previous-date="sampleFlowBaseDate" require-previous placeholder="选择日期" missing-previous-reason="请先填写送样日期或补全委托日期。" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">样品处理方式</label><div class="col"><el-select v-model="s.sampleHandle" filterable allow-create default-first-option clearable placeholder="选择/输入"><el-option v-for="o in SAMPLE_OPTS.sampleHandle" :key="o" :label="o" :value="o" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告交付方式</label><div class="col"><el-select v-model="s.deliverWay" filterable allow-create default-first-option clearable placeholder="选择/输入"><el-option v-for="o in SAMPLE_OPTS.deliverWay" :key="o" :label="o" :value="o" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">邮寄地址</label><div class="col"><el-input v-model="s.mailAddr" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告交付份数（只填数字）</label><div class="col"><el-input v-model="s.deliverStd" inputmode="numeric" maxlength="3" :formatter="digitsOnly"><template #append>份</template></el-input></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">报告形式</label><div class="col"><el-select v-model="s.reportForm" filterable allow-create default-first-option clearable placeholder="选择/输入"><el-option v-for="o in SAMPLE_OPTS.reportForm" :key="o" :label="o" :value="o" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">现场检测时间约定</label><div class="col"><el-select v-model="s.fieldAgreement" filterable allow-create default-first-option clearable placeholder="选择/输入"><el-option v-for="o in SAMPLE_OPTS.fieldAgreement" :key="o" :label="o" :value="o" /></el-select></div></div></div>
            <div class="col-12 col-lg-4"><div class="d-flex flex-column gap-1"><label class="form-label mb-1">约定检测日期</label><div class="col"><WorkflowDatePicker v-model="s.innerStdDate" :previous-date="sampleFlowBaseDate" require-previous placeholder="选择日期" missing-previous-reason="请先填写送样日期或补全委托日期。" /></div></div></div>
          </div>
        </div></details>
          </el-collapse-item>
        </el-collapse>
        </template>
      </el-form>
    </div>
    </fieldset>
    <!-- Preview is a read action, outside the disabled editing fieldset. -->
    <div v-if="mode === 'samples'" class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <el-button :loading="previewing" :disabled="!sampleEntrustNo || submitting || sampleFormLoading || Boolean(sampleFormError)" @click="openEntrustPreview">预览委托单</el-button>
    </div>

    <template #footer>
      <template v-if="readOnly">
        <el-button @click="requestClose">关闭</el-button>
      </template>
      <template v-else-if="mode === 'entrust'">
        <el-button type="primary" :loading="submitting" @click="saveEntrust">{{ isEntrustEdit ? '保存修改' : '保存' }}</el-button>
        <el-button v-if="canCompleteEntrust" type="success" :loading="submitting" @click="completeEntrustRegistration">完成登记</el-button>
        <el-button v-if="canUndoEntrust" type="warning" plain :loading="submitting" @click="undoEntrustCompletion">撤销完成</el-button>
        <el-button @click="requestClose">返回</el-button>
      </template>
      <template v-else>
        <template v-if="!legacyMigrationHold && !isChange">
          <el-button v-if="canCompleteSampleRegistration" type="success" :loading="submitting" @click="saveSamples('登记完成')">完成登记</el-button>
          <el-button type="primary" plain :loading="submitting" @click="saveSamples('登记中')">保存样品单</el-button>
        </template>
        <template v-else-if="!legacyMigrationHold">
          <el-button v-if="!inPlace && !administratorEditing" type="primary" plain :loading="submitting" @click="saveSampleChange('save')">保存修改</el-button>
          <el-button type="primary" :loading="submitting" @click="saveSamples()">{{ inPlace || administratorEditing ? '保存修改' : '提交更改完成' }}</el-button>
        </template>
        <el-button :disabled="!effectiveReportNo || legacyMigrationHold" @click="wizardAttachmentOpen = true">附件管理</el-button>
        <el-button :loading="previewing" :disabled="!sampleEntrustNo || submitting || sampleFormLoading || Boolean(sampleFormError)" @click="openEntrustPreview">预览委托单</el-button>
        <el-button :loading="previewing" :disabled="!sampleEntrustNo || previewing || submitting || sampleFormLoading || Boolean(sampleFormError)" @click="openEntrustExport">导出委托单 PDF</el-button>
        <el-button @click="requestClose">返回</el-button>
      </template>
    </template>

    <el-dialog v-model="draftDecisionOpen" :title="mode === 'entrust' ? '未保存的委托信息' : '未保存的样品信息'" width="460px" append-to-body :close-on-click-modal="false" :show-close="false">
      <p >当前表单有未保存修改，请选择处理方式。</p>
      <template #footer>
        <el-button @click="continueEditing">继续编辑</el-button>
        <el-button type="danger" plain @click="discardAndClose">放弃修改</el-button>
      </template>
    </el-dialog>

    <!-- 选择检测方案（按部门，方案编号进报告号） -->
    <el-dialog v-model="schemeDialogOpen" title="选择检测方案（按部门）" width="1100px" append-to-body >
      <div class="mb-3"><label class="form-label">方案名称 / 编号</label><el-input v-model="schemeKeyword" clearable placeholder="搜索方案名称 / 编号" /></div>
      <div class="list-group">
        <section v-for="grp in schemeTree" :key="grp.dept" class="mb-4">
          <h6 class="bg-light p-3 mb-3">{{ grp.dept }}</h6>
          <div class="row g-2">
          <button v-for="sc in grp.schemes" :key="sc.code" type="button" class="btn btn-light text-start col-12 col-md-6 d-flex align-items-center justify-content-between gap-2" @click="pickScheme(sc)">
            <span >{{ sc.name }}</span>
            <el-tag size="small" type="info">{{ sc.code }}</el-tag>
          </button>
          </div>
        </section>
        <el-empty v-if="!schemeTree.length" description="无匹配检测方案" :image-size="48" />
      </div>
    </el-dialog>

    <!-- 检测依据使用独立搜索窗口，确认后才统一更新样品及能力项目。 -->
    <BootstrapModal v-if="basisDialogOpen" :open="basisDialogOpen" title="选择检测依据标准"
      size="xl" scrollable fullscreen-mobile fill-height :loading="stdLoading" :busy="capabilityLoading"
      body-class="p-0 mx-3 overflow-auto" @close="basisDialogOpen = false">
      <template #toolbar>
      <form class="py-3" aria-label="检测依据查询" @submit.prevent="runBasisSearchFromStart">
        <label for="sample-basis-keyword" class="form-label">标准编号或名称</label>
        <el-input
          id="sample-basis-keyword"
          v-model="basisKeyword"
          clearable
          autofocus
          placeholder="输入标准编号或标准名称，例如 GB/T 10294"
          @clear="runBasisSearchFromStart"
        >
          <template #append><el-button type="primary" native-type="submit" :loading="stdLoading"><i class="ti ti-search me-1" aria-hidden="true"></i>搜索</el-button></template>
        </el-input>
        <div class="d-flex flex-wrap align-items-center gap-3 mt-3">
          <el-radio-group v-model="basisScopeFilter" size="small" @change="runBasisSearchFromStart">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="cnas">CNAS 范围</el-radio-button>
            <el-radio-button value="cma">CMA 范围</el-radio-button>
            <el-radio-button value="single">一单一库</el-radio-button>
          </el-radio-group>
          <el-checkbox v-model="basisSelectedOnly" @change="runBasisSearchFromStart">只显示已选标准</el-checkbox>
          <el-checkbox v-model="basisCapabilityOnly" @change="runBasisSearchFromStart">只看有能力项目</el-checkbox>
        </div>
        <p class="text-muted small mt-2 mb-0" role="status">
          当前条件：{{ s.testDept || '当前账号所属部门' }} · 参数类型不限
          · 同编号标准按记录独立选择，可同时选择中英文 · {{ basisSelectedOnly ? '已选标准筛选结果' : '现行授权标准' }} {{ basisVisibleTotal }} 条
        </p>
      </form>
      </template>
      <el-alert v-if="basisError" :title="basisError" type="error" :closable="false" />
      <el-table
        v-else
        :data="basisDialogRows"
        :row-key="(row: StdLibHit) => row.id || row.code"
        stripe
        border
        empty-text="没有符合当前条件的现行标准"
        aria-label="检测依据标准"
      >
        <el-table-column label="选择" width="68" align="center" fixed>
          <template #default="{ row }">
            <el-checkbox
              :model-value="basisDraftItemIds.includes(row.id)"
              :aria-label="`选择标准 ${row.code} ${row.name}`"
              @change="toggleBasisDraft(row, Boolean($event))"
            />
          </template>
        </el-table-column>
        <el-table-column prop="code" label="标准编号" min-width="170" sortable show-overflow-tooltip />
        <el-table-column prop="name" label="标准名称" min-width="310" show-overflow-tooltip />
        <el-table-column label="资质范围" width="210">
          <template #default="{ row }">
            <div class="d-flex flex-wrap gap-2">
              <el-tag size="small" :type="row.cnas ? 'success' : 'info'" effect="plain">{{ row.cnas ? 'CNAS' : '非CNAS' }}</el-tag>
              <el-tag size="small" :type="row.cma && row.singleList ? 'primary' : (row.cma ? 'warning' : 'info')" effect="plain">{{ cmaScopeLabel(row) }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="能力类型 / 场所" min-width="190">
          <template #default="{ row }">
            <div class="text-muted small">
              <span>{{ row.capabilityTypes?.join('、') || '未维护参数' }}</span>
              <small v-if="row.location" class="d-block">维护地点：{{ row.location }}</small>
              <small v-if="row.sites?.length" class="d-block">授权场所：{{ row.sites.join('、') }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="使用部门" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.useDepts?.join('、') || '—' }}</template>
        </el-table-column>
      </el-table>

      <template #pagination>
        <el-pagination
          v-model:current-page="basisPage"
          v-model:page-size="basisPageSize"
          :page-sizes="[20, 50, 100]"
          :total="basisVisibleTotal"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="queryBasisStandards"
          @size-change="runBasisSearchFromStart"
        />
      </template>
      <details v-if="basisDraftCodes.length" class="my-3" open>
        <summary class="fw-medium mb-2">已选择 {{ basisDraftRecords.length }} 项标准</summary>
        <p class="text-muted small">拖动或使用上下移按钮调整委托单中的顺序，确认后生效。</p>
        <OrderedSelectionList :items="basisDraftRecords.map(row => ({ key: row.key, label: `${row.code} · ${row.name}` }))"
          label="已选检测依据排序" @reorder="reorderBasisDraft" @remove="removeBasisDraft" />
      </details>

      <template #footer>
        <span class="me-auto text-muted" role="status">已选 {{ basisDraftRecords.length }} 项</span>
        <el-button v-if="basisDraftCodes.length" text type="danger" @click="basisDraftCodes = []; basisDraftItemIds = []">清空</el-button>
        <el-button @click="basisDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="capabilityLoading" :disabled="stdLoading || Boolean(basisError)" @click="confirmBasisSelection">确认选择（{{ basisDraftRecords.length }}）</el-button>
      </template>
    </BootstrapModal>

    <CapabilityPicker v-model="capabilityDialogOpen" :rows="capabilityCurrentRows" :selected-ids="s.capabilityEntryIds"
      :manual-locations="s.manualParameterLocations" :legacy-manual-location="s.manualTestLocation" :onsite="s.isOnsiteTesting" :location-options="manualLocationOptions" :locations-loading="manualLocationsLoading" :locations-error="manualLocationsError" @retry-locations="loadManualLocations"
      :standards="s.testBases" :catalog-locations="capabilityLocations" :manual-items="s.manualCapabilityItems" :item-order="s.testItemOrder" :history-rows="s.capabilitySnapshots" :selected-rows="capabilityCatalogSelections" :total="capabilityTotal" :context-key="selectionContext()" :loading="catalogLoading" :error="catalogError"
      @confirm="confirmCapabilitySelection" @query="loadCapabilityCatalog" @retry="loadCapabilityCatalog()" />
    <!-- 已有表单复制：搜索保存过的委托/样品，一键复制 -->
    <el-dialog v-model="copyDialogOpen" :title="mode === 'entrust' ? '已有委托复制' : '已有样品复制'" width="1100px" append-to-body  :class="{}">
      <el-input v-model="copyKeyword" clearable :placeholder="mode === 'entrust' ? '搜索委托编号 / 委托单位 / 工程名称 / 外部ERP合同编号' : '搜索样品编号 / 报告编号 / 委托单位 / 检测项目'" />
      <p v-if="mode === 'samples'">已保存样品库：包含全部流程状态，按数据权限显示。仅复制表单内容，不复制编号、检测结果和签章。</p>
      <el-alert v-if="copyError" :title="copyError" type="error" :closable="false" />
      <div v-loading="copyLoading" class="list-group">
        <template v-if="mode === 'entrust'">
          <button v-for="e in filteredCopyEntrusts" :key="e.entrustNo" type="button" class="list-group-item list-group-item-action d-flex flex-column gap-2 py-3" @click="copyFromEntrust(e)">
            <strong>{{ e.entrustNo }}</strong>
            <span>{{ e.client }} / {{ e.projectName }}</span>
            <small>{{ e.contractNo }} · {{ e.status }} · {{ e.date }}</small>
          </button>
          <el-empty v-if="!filteredCopyEntrusts.length && !copyLoading" description="无保存过的委托单" :image-size="48" />
        </template>
        <template v-else>
          <button v-for="r in filteredCopySamples" :key="r.reportNo" type="button" class="list-group-item list-group-item-action d-flex flex-column gap-2 py-3" :disabled="copyLoading" @click="copyFromSample(r)">
            <strong>{{ r.sampleNo }}</strong>
            <span>{{ r.client }} / {{ r.project }}</span>
            <small>{{ r.reportNo }} · {{ r.voided ? '已作废（仅复制资料）' : r.archiveState === '归档完成' ? '已归档' : r.status }} · {{ r.sampleStatus }}</small>
          </button>
          <el-empty v-if="!filteredCopySamples.length && !copyLoading && !copyError" description="当前权限范围内没有匹配的已保存样品" :image-size="48" />
        </template>
      </div>
      <template #footer>
        <el-pagination v-if="mode === 'samples'" :current-page="copyPage" :page-size="50" :total="copyTotal" layout="total, prev, pager, next" :disabled="copyLoading" @current-change="changeCopyPage" />
        <el-button v-if="copyError" @click="loadCopySamples">重试</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="entrustExportOpen" title="选择委托单导出版本" width="min(560px, calc(100vw - 32px))" append-to-body :close-on-click-modal="false" :close-on-press-escape="!previewing" :show-close="!previewing">
      <p>选择本次导出的版本。扩展版为加长版，无需先打开预览；不会更改报告封面模板。</p>
      <el-radio-group v-model="exportTemplateKind" :disabled="previewing" aria-label="委托单导出版本" >
        <el-radio v-for="option in BUSINESS_FORM_TEMPLATE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</el-radio>
      </el-radio-group>
      <div class="mt-2">
        <el-radio-group v-model="exportLanguage" :disabled="previewing" aria-label="导出字段语言">
          <el-radio v-for="option in entrustLanguages" :key="option.value" :value="option.value">{{ option.label }}</el-radio>
        </el-radio-group>
      </div>
      <p v-if="previewing" role="status">{{ entrustPreviewMessage }}</p>
      <template #footer>
        <el-button :disabled="previewing" @click="entrustExportOpen = false">取消</el-button>
        <el-button type="primary" :loading="previewing" :disabled="submitting || sampleFormLoading || Boolean(sampleFormError) || !sampleEntrustNo" @click="confirmEntrustExport">确认导出 PDF</el-button>
      </template>
    </el-dialog>

    <!-- 当前样品自己的委托信息预览；修改不会影响原委托或其他样品。 -->
    <el-dialog v-model="coverPreviewOpen" title="样品委托单预览（当前样品独立信息）" width="900px" append-to-body >
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <span>委托单模板</span>
        <el-segmented
          v-model="previewTemplateKind"
          :options="BUSINESS_FORM_TEMPLATE_OPTIONS"
          size="small"
          :disabled="previewing"
          @change="onPreviewTemplateChange"
        />
        <el-button size="small" :loading="previewing" @click="onPreviewEntrust">刷新预览</el-button>
      </div>
      <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
        <span>检测类别和日期</span>
        <el-segmented v-model="previewLanguage" :options="entrustLanguages" size="small" aria-label="预览字段语言" :disabled="previewing" @change="onPreviewEntrust" />
      </div>
      <CommissionPdfPages :url="coverPdfUrl" :filename="`${s.sampleNo || sampleReportNo || 'sample'}-WT-${previewTemplateKind}${previewLanguage === 'CN' ? '' : '-' + previewLanguage}.pdf`" :disabled="previewing || !coverPreviewOpen" :before-download="validateEntrustPreviewDownload" />
      <DataEntryPreview v-if="coverPdfUrl" :url="coverPdfUrl" title="样品委托单预览" name="" type="application/pdf" embedded compact persistent hide-download hide-print />
      <el-empty v-else :description="previewing ? entrustPreviewMessage : '暂无委托单预览'" />
    </el-dialog>
    <AttachmentManagerDialog v-model="wizardAttachmentOpen" :report-no="effectiveReportNo" :view="resolvedDetailView" :title="`附件管理 · ${effectiveReportNo}`" />
  </component>
</template>

<script setup lang="ts">
import TemplateEditableSelect from '../../components/common/TemplateEditableSelect.vue'
import SourceReportSelect from '../../platformUi/commissions/SourceReportSelect.vue'
import { sampleQuantityText, setSampleQuantity } from '../composables/sampleQuantity'
import CommissionPdfPages from './CommissionPdfPages.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import CapabilityPicker from '@/components/CapabilityPicker.vue'
import OrderedSelectionList from '@/components/OrderedSelectionList.vue'
import CommissionTextPreview from '@/components/CommissionTextPreview.vue'
import StandardTitleChoices from '../../platformUi/StandardTitleChoices.vue'
import JudgmentStandardDisplay from '../../platformUi/testing/JudgmentStandardDisplay.vue'
import { standardPreview, standardRecordPreview, type StandardDisplayRecord, type TitleStyle } from '../../platformUi/testing/reportTextDisplay'
import { reconcileTestItemOrder, testItemKey, testItemRows, type TestItemRef } from '@/composables/testItemOrder'
import JudgmentBasisInput from '@/components/JudgmentBasisInput.vue'
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import { computed, nextTick, onUnmounted, reactive, ref, watch } from 'vue'
import type { EntrustPreviewFile } from '@/services/pipeline'
// BEGIN TEMPLATE SAMPLE_LAYOUT IMPORTS
import { ElDialog } from 'element-plus'
import SampleFormSurface from '../../platformUi/commissions/SampleFormSurface'
import EntrustSelection from '../../platformUi/commissions/EntrustSelection'
import ContractSelection from '../../platformUi/commissions/ContractSelection'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
// END TEMPLATE SAMPLE_LAYOUT IMPORTS

import { ElMessage, ElMessageBox } from 'element-plus'
import {
  BUSINESS_FORM_TEMPLATE_OPTIONS,
  createReport, createEntrust, updateEntrust, completeEntrust, uncompleteEntrust, editReportInPlace, sampleRegAction, fetchContractSelectionPage, fetchDepartments, fetchEntrustOptions, fetchNextEntrustNo, fetchHandleDepartments,
  previewSampleEntrust, fetchSchemes, fetchCapabilityItems, fetchCapabilityPage,
  fetchEntrustList, changeResubmit, saveEntrustChange, validateSampleConfiguration,
  type Agreement, type AgreementDepartment, type EntrustOption, type EntrustSnapshot, type SchemeNode, type SchemeRow, type CapabilityItemRow,
  type EntrustOrder, type SampleRow, type Customer, type SampleListView, type BusinessFormTemplateKind,
} from '@/services/pipeline'
import { fetchReportDetail, fetchSampleFormImage, type ReportDetailView } from '@/services/reports'
import { fetchSampleCopyPage, fetchSampleCopySource, type SampleCopyRow } from '@/services/sampleCopies'
import { searchStdLib, searchStdLibPage, type StdLibHit } from '@/services/quality'
import { rememberCorrection } from '@/services/businessCorrection'
import { useSessionStore } from '@/stores/session'
import AttachmentManagerDialog from '@/components/AttachmentManagerDialog.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import ProductionDatesEditor from '@/components/ProductionDatesEditor.vue'
import SampleSubprojectEditor from '@/components/SampleSubprojectEditor.vue'
import TechnicalSubprojectPicker from '@/components/TechnicalSubprojectPicker.vue'
import { technicalSummary, type TechnicalSubproject } from '@/services/technicalSubprojects'
import { normalizeSubprojects, parseLegacySubprojects, samplePricingErrors, subprojectSummary, type SampleSubproject } from '@/composables/sampleSubprojects'
import AiVoiceDraft from '@/components/AiVoiceDraft.vue'
import CustomerPicker from '@/components/CustomerPicker.vue'
import RegistrarPicker from '../../platformUi/commissions/RegistrarPicker.vue'
import type { RegistrarOption } from '@/services/registrarDirectory'
import { customerContactFields } from '@/services/customerDirectory'
import type { AiFormPatch } from '@/services/ai'
import { businessToday, isWorkflowDateBefore, isWorkflowDateValid } from '@/composables/workflowDate'
import type { ProductionDateRow } from '@/composables/productionDates'
import { dateBoundary, savedSampleDates, sampleDateOrderErrors, productionDateBoundary, isProductionDateValid } from '@/composables/sampleDateRules'
import { actualParameterAddresses, type ManualParameterLocations } from '@/data/parameterLocations'
import { fetchTestingLocations } from '@/services/pipeline'
import {
  CAPABILITY_SITE_FULL_ADDRESSES,
  capabilitySiteForAddress,
  commonCapabilitySites,
  fullAddressesForSites,
} from '@/data/capabilityLocations'

const session = useSessionStore()
const props = withDefaults(defineProps<{ modelValue: boolean; pageView?: boolean; embeddedSection?: 'commission' | 'sample'; department?: string; mode?: 'entrust' | 'samples'; presetEntrustNo?: string; changeReportNo?: string; inPlace?: boolean; editEntrust?: EntrustOrder | null; readOnly?: boolean; sampleListView?: SampleListView; detailView?: ReportDetailView }>(), {
  mode: 'entrust',
  readOnly: false,
  sampleListView: 'flow_query',
})
const resolvedDetailView = computed<ReportDetailView>(() => props.detailView ?? ({
  register: 'sample_register',
  inbound: 'sample_inbound',
  outbound: 'sample_outbound',
  flow_query: 'sample_flow_query',
} as const)[props.sampleListView])
// 更改模式：传入要更改的报告号 → 用完整表单预填该报告的委托/样品信息
// inPlace=true：就地修改（直接保存、不重走评审）；false：走更改评审流程
const administratorEditing = ref(false)
const readOnly = computed(() => session.businessReadOnly || (!administratorEditing.value && (
  props.readOnly || (props.mode === 'entrust' && entrustCompleted.value)
  || (props.mode === 'samples' && props.inPlace && !!effectiveReportNo.value && activeSampleRegState.value !== '登记中')
)))
let administratorBaseline = ''
const administratorSnapshot = () => JSON.stringify({ f, s, sampleEntrust, correctedReportNo: correctedReportNo.value })
async function toggleAdministratorEditing() {
  if (!session.canCorrectBusinessData || session.businessReadOnly || submitting.value) return
  if (administratorEditing.value) {
    if (administratorSnapshot() !== administratorBaseline) {
      try { await ElMessageBox.confirm('退出将放弃进入管理员编辑后尚未保存的修改。是否退出？', '退出管理员编辑', { type: 'warning' }) } catch { return }
      const saved = JSON.parse(administratorBaseline)
      Object.assign(f, saved.f); Object.assign(s, saved.s); Object.assign(sampleEntrust, saved.sampleEntrust)
      correctedReportNo.value = saved.correctedReportNo
    }
    sampleSelectedContract.value = undefined
    administratorEditing.value = false
  } else {
    administratorBaseline = administratorSnapshot()
    administratorEditing.value = true
  }
}
watch(() => [props.modelValue, props.changeReportNo, props.editEntrust?.id, props.mode, session.account, session.canCorrectBusinessData], () => {
  administratorEditing.value = false
  sampleSelectedContract.value = undefined
})
const isChange = computed(() => !!props.changeReportNo)
const activeSavedReportNo = ref('')
const sampleConfirmedContractNo = ref('')
const legacyMigrationHold = ref(false)
watch(() => [props.modelValue, props.changeReportNo, props.mode], () => { legacyMigrationHold.value = false })
// A persistent wizard can be reopened for another record while an old request
// is still running. Only the session that started a request may apply its result.
let sampleFormEpoch = 0
function sampleFormSession() {
  const epoch = sampleFormEpoch
  const target = props.changeReportNo
  const mode = props.mode
  const entrustId = props.editEntrust?.id
  return () => props.modelValue && epoch === sampleFormEpoch && target === props.changeReportNo
    && mode === props.mode && entrustId === props.editEntrust?.id
}
const effectiveReportNo = computed(() => props.changeReportNo || activeSavedReportNo.value)
const derivedSchemeLocked = computed(() => s.reportCategory !== '普通' && !!s.baseReportNo)
const schemeLocked = computed(() => derivedSchemeLocked.value || props.mode === 'samples' && !!effectiveReportNo.value && !administratorEditing.value)
const activeEntrustId = ref<number | null>(null)
const activeEntrustStatus = ref('委托中')
const activeEntrustCompletionAccount = ref('')
const activeSampleRegState = ref('登记中')
const isEntrustEdit = computed(() => activeEntrustId.value !== null)
const entrustCompleted = computed(() => activeEntrustStatus.value === '委托完成')
const entrustStatusLabel = computed(() => entrustCompleted.value ? '已完成' : '登记中')
const canCompleteEntrust = computed(() => !entrustCompleted.value && (
  session.can('entrust.registration.view')
  || session.canAction('entrust.register.complete')
))
const canUndoEntrust = computed(() => (
  entrustCompleted.value
  && (activeEntrustCompletionAccount.value === session.account || session.account === 'admin' || (session.fullPlatformAuthority || session.roleKey === 'admin'))
  && session.can('entrust.registration.view')
))
const canCompleteSampleRegistration = computed(() => (
  session.can('entrust.sample_register.view')
  || session.canAction('sample.register.complete')
))
const dialogTitle = computed(() => {
  if (administratorEditing.value) return props.mode === 'samples'
    ? `管理员编辑样品 · ${effectiveReportNo.value || sampleReportNo.value || ''}`
    : `管理员编辑委托 · ${f.entrustNo || ''}`
  if (readOnly.value) {
    return props.mode === 'samples'
      ? `查看样品 · ${effectiveReportNo.value || sampleReportNo.value || ''}`
      : `查看委托 · ${f.entrustNo || props.editEntrust?.entrustNo || ''}`
  }
  if (props.mode === 'samples') {
    if (props.changeReportNo) return `样品更改 · ${props.changeReportNo}（修改后提交）`
    return activeSavedReportNo.value ? `样品登记 · ${activeSavedReportNo.value}` : '添加样品（选择委托单）'
  }
  return activeEntrustId.value ? `委托登记 · ${f.entrustNo || props.editEntrust?.entrustNo || ''}` : '新增委托信息'
})
const emit = defineEmits<{ 'update:modelValue': [boolean]; created: [string]; 'entrust-created': [string]; updated: [string]; 'entrust-updated': [string] }>()

const submitting = ref(false)
const wizardAttachmentOpen = ref(false)

function applyVoiceDraft(patches: AiFormPatch[]) {
  const target = props.mode === 'entrust' ? f : s
  for (const patch of patches) {
    if (Object.prototype.hasOwnProperty.call(target, patch.path)) {
      ;(target as unknown as Record<string, unknown>)[patch.path] = patch.value
    }
  }
  if (props.mode === 'samples' && Array.isArray(s.testBases)) s.testBasis = s.testBases.join('；')
}

// ---- 委托表单 ----
function entrustBlank() {
  return {
    entrustNo: '', consignor: '', consignorPhone: '', entrustDate: '',
    contractNo: '', erpProjectNo: '', erpContractNo: '', erpType: '', projectType: '',
    contractPartyA: '', otherPartyA: '', client: '', clientAddr: '',
    clientLegal: '', clientPhone: '', clientZip: '',
    projectRecordNo: '', projectTradeCode: '', projectName: '', projectAddr: '',
    handleDept: '', handler: '', handlerPhone: '', sampleRegistrarUserId: '', sampleRegistrarDepartmentId: '',
    invoiceType: '', taxNo: '', companyName: '', bizAddr: '', bank: '', account: '',
  }
}
const f = reactive(entrustBlank())

const ENTRUST_REQUIRED = [
  ['client', '委托单位'], ['projectName', '项目名称'], ['entrustDate', '委托日期'],
  ['handleDept', '经办部门'], ['handler', '经办人'],
] as const
const entrustErrors = reactive<Record<string, string>>({})
const entrustErrorList = computed(() => ENTRUST_REQUIRED.filter(([key]) => entrustErrors[key]).map(([, label]) => label))
const initialEntrustSnapshot = ref('')
const draftSavedAt = ref('')
const draftDecisionOpen = ref(false)
let pendingCloseAction: (() => void) | null = null
const draftKey = computed(() => `lims:entrust-draft:${session.account || 'current'}`)
const entrustDirty = computed(() => JSON.stringify(f) !== initialEntrustSnapshot.value)
const initialSampleSnapshot = ref('')
const judgmentInput = ref<InstanceType<typeof JudgmentBasisInput>>()
const sampleSnapshot = () => JSON.stringify({ entrustNo: sampleEntrustNo.value, entrust: sampleEntrust, form: s, list: samples, correctedReportNo: correctedReportNo.value })
const sampleDirty = computed(() => props.mode === 'samples' && (judgmentInput.value?.hasPending || sampleSnapshot() !== initialSampleSnapshot.value))

function clearEntrustErrors() {
  Object.keys(entrustErrors).forEach((key) => delete entrustErrors[key])
}
function validateEntrust() {
  clearEntrustErrors()
  for (const [key, label] of ENTRUST_REQUIRED) {
    if (!String(f[key] || '').trim()) entrustErrors[key] = `请填写${label}`
  }
  if (f.entrustDate && !isWorkflowDateValid(f.entrustDate)) {
    entrustErrors.entrustDate = '委托日期格式无效'
  }
  if (!entrustErrorList.value.length) return true
  void nextTick(() => {
    const first = ENTRUST_REQUIRED.find(([key]) => entrustErrors[key])?.[0]
    document.querySelector(`[data-ui~=entrust-dialog] [data-field="${first}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
  return false
}
watch(f, () => {
  for (const [key] of ENTRUST_REQUIRED) {
    if (String(f[key] || '').trim()) delete entrustErrors[key]
  }
}, { deep: true })

function restoreDraft() {
  if (props.editEntrust || typeof sessionStorage === 'undefined') return
  const raw = sessionStorage.getItem(draftKey.value)
  if (!raw) return
  try {
    const draft = JSON.parse(raw) as { savedAt?: string; values?: ReturnType<typeof entrustBlank> }
    if (draft.values) Object.assign(f, entrustBlank(), draft.values)
    draftSavedAt.value = draft.savedAt || ''
  } catch {
    clearEntrustDraft()
  }
}
function clearEntrustDraft() {
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(draftKey.value)
  if (typeof localStorage !== 'undefined') localStorage.removeItem(draftKey.value)
  draftSavedAt.value = ''
}
function persistEntrustDraft() {
  const savedAt = new Date().toLocaleString('zh-CN', { hour12: false })
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(draftKey.value, JSON.stringify({ savedAt, values: { ...f } }))
  }
  if (typeof localStorage !== 'undefined') localStorage.removeItem(draftKey.value)
  draftSavedAt.value = savedAt
}
async function shouldRestoreEntrustDraft() {
  if (props.editEntrust || typeof sessionStorage === 'undefined' || !sessionStorage.getItem(draftKey.value)) return false
  try {
    await ElMessageBox.confirm(
      '发现本次登录中有未完成的委托，是否继续填写？',
      '未完成委托',
      {
        confirmButtonText: '继续未完成委托',
        cancelButtonText: '删除缓存并新建',
        distinguishCancelAndClose: false,
        closeOnClickModal: false,
        closeOnPressEscape: false,
        showClose: false,
        type: 'info',
      },
    )
    return true
  } catch {
    clearEntrustDraft()
    return false
  }
}
function finishPendingClose() {
  const close = pendingCloseAction
  pendingCloseAction = null
  draftDecisionOpen.value = false
  close?.()
}
function requestCloseWith(action: () => void) {
  if (readOnly.value) {
    action()
    return
  }
  if (props.mode === 'entrust' && !isEntrustEdit.value) {
    persistEntrustDraft()
    initialEntrustSnapshot.value = JSON.stringify(f)
    pendingCloseAction = null
    draftDecisionOpen.value = false
    action()
    return
  }
  if ((props.mode === 'entrust' && entrustDirty.value) || sampleDirty.value) {
    pendingCloseAction = action
    draftDecisionOpen.value = true
    return
  }
  action()
}
function handleDialogBeforeClose(done: () => void) {
  requestCloseWith(() => {
    done()
    emit('update:modelValue', false)
  })
}
function requestClose() { requestCloseWith(() => emit('update:modelValue', false)) }
function continueEditing() { pendingCloseAction = null; draftDecisionOpen.value = false }
function discardAndClose() {
  if (props.mode === 'entrust') {
    Object.assign(f, entrustBlank())
    clearEntrustDraft()
    initialEntrustSnapshot.value = JSON.stringify(f)
  } else {
    Object.assign(s, sampleBlank())
    Object.assign(sampleEntrust, entrustBlank())
    samples.splice(0, samples.length)
    sampleEntrustNo.value = ''
    initialSampleSnapshot.value = sampleSnapshot()
  }
  finishPendingClose()
}

interface HandleDepartmentOption {
  id: number
  name: string
  fullName: string
}

const handleDepts = ref<HandleDepartmentOption[]>([])
const organizationDepartments = ref<AgreementDepartment[]>([])

function findOrganizationDepartment(value: string) {
  const source = String(value || '').trim()
  if (!source) return undefined
  const exact = organizationDepartments.value.filter((department) => (
    source === department.name || source === department.fullName
  ))
  if (exact.length === 1) return exact[0]
  const leaf = organizationDepartments.value.filter((department) => source === department.leafName)
  return leaf.length === 1 ? leaf[0] : undefined
}

function organizationDisplayName(value: unknown) {
  const source = String(value || '').trim()
  return findOrganizationDepartment(source)?.fullName || source
}

function ensureHandleDepartmentOption(value: string, displayName = '') {
  const source = String(value || '').trim()
  const organization = findOrganizationDepartment(source)
  const name = organization?.name || source
  if (!name) return ''
  if (!handleDepts.value.some((department) => department.name === name)) {
    handleDepts.value.push({
      id: -(handleDepts.value.length + 1),
      name,
      fullName: organization?.fullName || String(displayName || '').trim() || name,
    })
  }
  return name
}

// Only the selected contract is retained here; the picker searches server pages.
const claimedContracts = ref<Agreement[]>([])
const selectedContract = computed(() => claimedContracts.value.find((item) => item.agreementNo === f.contractNo))
const selectedContractType = computed(() => String(
  selectedContract.value?.erpType || selectedContract.value?.contractType || f.erpType || '',
))
const contractPartyALocked = computed(() => {
  const type = selectedContractType.value
  return !type.includes('虚拟框架') && (type.includes('标准') || type.includes('框架'))
})
function resetContractUnits(client = '') {
  f.contractPartyA = client
  f.otherPartyA = client
  f.client = client
}
function onContractSelected(contract?: Agreement) {
  claimedContracts.value = contract ? [contract] : []
  f.contractNo = contract?.agreementNo || ''
  onPickContract(f.contractNo)
}
function onPickContract(no: string) {
  const c = claimedContracts.value.find((x) => x.agreementNo === no)
  if (!c) {
    resetContractUnits()
    f.erpProjectNo = ''
    f.erpContractNo = ''
    f.erpType = ''
    f.projectType = ''
    return
  }
  f.erpProjectNo = c.projectCode || c.erpProjectNo || ''
  f.erpContractNo = c.agreementNo
  f.erpType = c.erpType
  f.projectType = c.category || c.erpType
  resetContractUnits(c.client)
  f.projectName = c.projectName
}

// 客户库只在选择窗口打开时加载；仅明确确认单个客户时带出资料。
function onPickClient(rows: Customer[]) {
  const fields = customerContactFields(rows)
  if (fields) Object.assign(f, fields)
}
function onPickSampleClient(rows: Customer[]) {
  const fields = customerContactFields(rows)
  if (fields) Object.assign(sampleEntrust, fields)
}

// ---- 样品（按委托单） ----
// 检测中心 + 各自可出具的报告类型（与封面/首页模板完全对应）
const centers = [
  { name: '空调中心', prefix: 'NCSA', types: ['产品报告', '工程报告', '抽样报告'] },
  
  
  
  
  { name: '示例中心', prefix: 'LAB', types: ['产品报告', '工程报告', '抽样报告', '检验（检查）报告', '校准报告'] },
]
// 空调中心默认加 CMA + CNAS，可显式选择不加 CMA；加载历史表单时保留其已存要求。
const sealByCenter = (prefix: string) => (prefix === 'LAB' ? 'CNAS' : 'CMA + CNAS')

// 样品登记各下拉字段的可选项（可下拉选，也允许手输）
const SAMPLE_OPTS: Record<string, string[]> = {
  testCategory: ['委托', '委托（有见证送检）', '型式检验', '型式试验', '抽样检测', '抽样型式检验'],
  dept: ['综合业务部', '热工系统检测部', '建筑光学检测部', '净化技术检测部', '建筑热工检测部', '空调及净化系统工程检测部', '绿建检测一部', '围护结构检测部', '综合检测部', '建筑智能电气检测部', '供暖设备检测部', '热工设备检测部', '空调设备检测部'],
  // 检测类别：委托 / 校准 / 抽样（对应报告封面检测类别）
  taskSource: ['委托', '抽样', '监督抽查', '政府委托'],
  // 委托方要求（按真实系统下拉）
  sampleHandle: ['客户取回', '中心处置', '委托中心托运'],
  deliverWay: ['自取', '邮寄', '其他'],
  reportForm: ['单页', '多页'],
  fieldAgreement: ['正常', '客户指定', '联系后确认'],
  appearance: ['正常', '异常'],
  nameplate: ['有', '无'],
  // 缴费情况
  payStatus: ['委托时缴纳', '取报告时缴纳', '委托时已缴费合同额'],
}
type WorkflowEntrustOption = EntrustOption & {
  entrustDate?: string
  workflowDates?: { entrustAt?: string }
}
const entrustOptions = ref<WorkflowEntrustOption[]>([])
const sampleEntrustNo = ref('')
const sampleEntrust = reactive(entrustBlank())
const inheritedEntrustSnapshot = ref<EntrustSnapshot>()
const sampleSelectedContract = ref<Agreement>()
const canSelectSampleContract = computed(() => !readOnly.value && (
  administratorEditing.value || isChange.value || activeSampleRegState.value === '登记中'
))
function onSampleContractSelected(contract?: Agreement) {
  if (!canSelectSampleContract.value || submitting.value) return
  if (!contract) return ElMessage.warning('样品必须保留关联合同，请选择另一份已登记合同')
  if (contract.agreementNo === sampleEntrust.contractNo) return
  sampleSelectedContract.value = contract
  Object.assign(sampleEntrust, {
    contractNo: contract.agreementNo, erpContractNo: contract.agreementNo,
    erpProjectNo: contract.projectCode || contract.erpProjectNo || '',
    erpType: contract.erpType || contract.contractType,
    projectType: contract.erpType || contract.contractType,
    projectName: contract.projectName, contractPartyA: contract.client,
  })
  if (s.subItems.some(item => item.source === 'erp' && item.contractNo !== contract.agreementNo)) {
    ElMessage.warning('已有外部ERP子项目属于原合同，已保留；请在子项目信息中移除或重新选择后保存')
  }
}
function applyCurrentSampleRegistrar() {
  if (readOnly.value || effectiveReportNo.value) return
  sampleEntrust.handleDept = session.dataScope.department || ''
  sampleEntrust.handler = session.userName || session.account || ''
}
function selectRegistrarPerson(person: RegistrarOption) {
  if (!administratorEditing.value || readOnly.value) return
  sampleEntrust.handler = person.name
  sampleEntrust.sampleRegistrarUserId = String(person.id)
  sampleEntrust.handleDept = person.department || ''
  sampleEntrust.sampleRegistrarDepartmentId = person.departmentId ? String(person.departmentId) : ''
}
function selectRegistrarDepartment(department: RegistrarOption) {
  if (!administratorEditing.value || readOnly.value) return
  sampleEntrust.handleDept = department.name
  sampleEntrust.sampleRegistrarDepartmentId = String(department.id)
}
const sampleContractType = computed(() => String(
  sampleEntrust.erpType
  || selectedEntrust.value?.info?.erpType
  || sampleEntrust.projectType
  || selectedEntrust.value?.projectType
  || '',
))
const sampleContractPartyALocked = computed(() => {
  const type = sampleContractType.value
  return !type.includes('虚拟框架') && (type.includes('标准') || type.includes('框架'))
})

function applySampleEntrustOption(option?: WorkflowEntrustOption) {
  sampleSelectedContract.value = undefined
  Object.assign(sampleEntrust, entrustBlank())
  if (!option) return
  Object.assign(sampleEntrust, option.info || {})
  sampleEntrust.entrustNo = option.entrustNo
  sampleEntrust.contractNo = option.contractNo || ''
  sampleEntrust.erpContractNo = option.contractNo || ''
  sampleEntrust.erpProjectNo = option.erpProjectNo || sampleEntrust.erpProjectNo
  sampleEntrust.client = option.client || sampleEntrust.client
  sampleEntrust.projectName = option.projectName || sampleEntrust.projectName
  sampleEntrust.projectType = option.projectType || sampleEntrust.projectType
  sampleEntrust.handleDept = option.department || sampleEntrust.handleDept
  sampleEntrust.handler = option.owner || sampleEntrust.handler
  sampleEntrust.entrustDate = sampleEntrust.entrustDate || option.entrustDate || option.workflowDates?.entrustAt || ''
  applyCurrentSampleRegistrar()
}

function onSampleEntrustChange(no: string) {
  inheritedEntrustSnapshot.value = undefined
  applySampleEntrustOption(entrustOptions.value.find((option) => option.entrustNo === no))
}

function sampleEntrustPayload(): EntrustSnapshot {
  applyCurrentSampleRegistrar()
  const option = selectedEntrust.value
  return {
    ...inheritedEntrustSnapshot.value,
    sourceEntrustId: option?.id ?? inheritedEntrustSnapshot.value?.sourceEntrustId,
    sourceEntrustNo: sampleEntrustNo.value,
    entrustNo: sampleEntrustNo.value,
    contractNo: sampleEntrust.contractNo || sampleEntrust.erpContractNo,
    client: sampleEntrust.client,
    projectName: sampleEntrust.projectName,
    projectType: sampleEntrust.projectType,
    amount: inheritedEntrustSnapshot.value?.amount ?? option?.amount ?? '',
    department: sampleEntrust.handleDept,
    owner: sampleEntrust.handler,
    info: { ...sampleEntrust },
  }
}
// Original sample options are loaded on demand by SourceReportSelect.
const today = businessToday()
const sampleBlank = () => ({
  // 送样信息：幕墙工程名称独立填写，检测类别默认委托。
  sampleNo: '', sampleName: '', engineeringName: '', project: '', projectList: [] as string[], spec: '', batch: '', manufacturer: '',
  testDept: '', testRoom: '', urgent: '否', deadline: '正常',
  sendDate: today, unit: '', appearance: '', nameplate: '',
  // 商标：文字 + 图样（base64，模板内按单元格等比缩放居中）
  trademark: '', trademarkImage: '',
  testType: '委托', reportType: '产品报告', testCategory: '委托',
  reportLanguage: 'CN', reportTemplateVariant: 'Standard',
  testLocation: '', sampleAmount: '', factoryNo: '', produceDate: '', productionDates: [] as ProductionDateRow[],
  isOnsiteTesting: false, onsiteTestLocation: '', manualTestLocation: '', manualParameterLocations: null as ManualParameterLocations | null, actualTestLocations: [] as string[], locationWorkflowVersion: 1,
  testPlan: '', standardJudge: '', judgmentEntries: undefined as string[] | undefined, seal: 'CMA + CNAS', centerPrefix: '',
  judgmentDisplay: { standardShowName: true, standardTitleStyles: {} as Record<string, TitleStyle>, standardSeparatorText: '；' },
  // 第三类：补充/英文/分项报告（基于原报告派生）
  reportCategory: '普通', baseReportNo: '', subSuffix: '',
  // 检测方案（按部门选，方案编号进报告号）+ 检测依据（标准库）
  basisSeparator: '；', basisTitleStyles: {} as Record<string, TitleStyle>, itemsSeparator: '、', commissionText: { basis: '', items: '' },
  schemeName: '', schemeCode: '', testBasis: '', testBases: [] as string[], testBasisSingle: false,
  standardItemId: 0, standardItemIds: [] as number[], standardRecords: [] as StandardDisplayRecord[], standardNames: {} as Record<string, string>,
  capabilityEntryIds: [] as number[], capabilitySnapshots: [] as CapabilityItemRow[],
  manualCapabilityItems: [] as string[], manualCapabilityReason: '', testItemOrder: [] as TestItemRef[],
  // 项目信息：备注拆为「委托单备注」「报告首页备注」（两份独立数据）
  remark: '', homepageRemark: '', innerRemark: '',
  // 抽样信息（委数→基数）+ 预留字段（抽样地点/编号/样品到达日期/等级/封样状态/检查封样人员）
  sampleUnit: '', sampler: '', sampleTime: '', sampleQty: '', entrustQty: '', inspectedUnit: '', taskSource: '',
  samplingLocation: '', samplingNo: '', sampleFormNo: '', sampleArrivalDate: '', sampleGrade: '', sealStatus: '', sealChecker: '',
  // 结算信息：仅标准价格 + 缴费情况 + 支付方式 + 已缴费 + 其他
  stdPrice: '', payStatus: '', payWay: '', paid: '', otherSettle: '',
  subItems: [] as SampleSubproject[],
  detectionSubprojects: [] as TechnicalSubproject[],
  // 报告发送
  sendOutTime: '', sendInTime: '', sampleHandle: '', deliverWay: '', mailAddr: '', deliverStd: '', reportForm: '', fieldAgreement: '', innerStdDate: '',
})
type SampleItem = ReturnType<typeof sampleBlank> & { reportNo: string; reportPrefix: string; entrustSnapshot: EntrustSnapshot }
const samples = reactive<SampleItem[]>([])
const s = reactive(sampleBlank())

function setJudgmentEntries(entries: string[]) {
  s.judgmentEntries = entries
  s.standardJudge = entries.join('；')
}
function judgmentFollows(bases: string[]) {
  const entries = s.judgmentEntries ?? splitBasisValues(s.standardJudge)
  return !entries.length || (entries.length === bases.length && entries.every((entry, index) => entry === bases[index]))
}
function followTestingBases() {
  if (s.judgmentEntries === undefined) {
    s.standardJudge = s.testBasis
    return
  }
  setJudgmentEntries([...s.testBases])
}
const correctedReportNo = ref('')
const sourceSample = ref<{ reportNo: string; sampleNo: string }>()
watch(() => s.baseReportNo, value => { if (sourceSample.value?.reportNo !== value) sourceSample.value = undefined }, { flush: 'sync' })
const sampleTestCategories = SAMPLE_OPTS.testCategory
const sampleDepartmentOptions = computed(() => Array.from(new Set(
  [s.testDept, ...SAMPLE_OPTS.dept].map((value) => value.trim()).filter(Boolean),
)))
const advancedSections = ref<string[]>([])
const configChecking = ref(false)
const sampleConfigErrors = ref<string[]>([])
const DERIVE_SUFFIX: Record<string, string> = { 补充: 'BC', 英文: '(E)' }
// 报告编号前缀：检测中心-年+检测方案编号（如 LAB-2026SYHR）；未选方案用 R 占位。序号由后端按同前缀顺序自动分配。
const reportPrefix = computed(() => (s.centerPrefix ? `${s.centerPrefix}-${today.slice(0, 4)}${s.schemeCode || 'R'}` : ''))
const sampleReportNo = computed(() => {
  if (administratorEditing.value && correctedReportNo.value.trim()) return correctedReportNo.value.trim()
  // 补充/英文/分项报告：原报告号 + 后缀（BC / (E) / -填空）
  if (s.reportCategory !== '普通' && s.baseReportNo) {
    if (s.reportCategory === '分项') return `${s.baseReportNo}-${s.subSuffix || '▢'}`
    return `${s.baseReportNo}${DERIVE_SUFFIX[s.reportCategory] || ''}`
  }
  // 已保存的样品继续沿用固定样品号，仅按当前报告标题预览新的报告编号前缀。
  if (effectiveReportNo.value && s.centerPrefix) return `${s.centerPrefix}-${effectiveReportNo.value.slice(effectiveReportNo.value.indexOf('-') + 1)}`
  if (props.changeReportNo) return props.changeReportNo
  if (activeSavedReportNo.value) return activeSavedReportNo.value
  // 普通报告：未保存时直接显示编号代码；最终序号仍由后端在保存时分配。
  return reportPrefix.value ? `${reportPrefix.value}-****` : ''
})
// 报告类型选项 = 当前检测中心可出具的类型（与模板一一对应）
const centerTypes = computed(() => centers.find((c) => c.prefix === s.centerPrefix)?.types ?? ['产品报告', '工程报告'])
watch(() => s.reportType, (kind) => {
  if (!['产品报告', '抽样报告'].includes(kind)) s.reportTemplateVariant = 'Standard'
  if (kind.includes('校准')) s.reportLanguage = 'CN'
})
// 切换检测中心：仅调整可用报告类型，盖章默认值由用户选择事件设置。
watch(() => s.centerPrefix, (p) => {
  if (!p) return
  const types = centers.find((c) => c.prefix === p)?.types ?? []
  if (types.length && !types.includes(s.reportType)) s.reportType = types[0]
})
// 登记界面统一为一个“检测部门/检测室”字段；继续镜像 testRoom，兼容既有模板与历史接口。
watch(() => s.testDept, (value) => { s.testRoom = value || '' }, { immediate: true })
// 外观 ↔ 封样状态 双向同步
watch(() => s.appearance, (v) => { if (s.sealStatus !== v) s.sealStatus = v })
watch(() => s.sealStatus, (v) => { if (s.appearance !== v) s.appearance = v })
// 样品到达日期始终采用送样日期；初始化、同日重开、复制和重置也必须同步。
watch(() => [s.sendDate, s.sampleArrivalDate], () => {
  if (s.sampleArrivalDate !== s.sendDate) s.sampleArrivalDate = s.sendDate
}, { immediate: true, flush: 'sync' })
// 商标图样：读为 base64 存入表单（模板内按单元格等比缩放居中）
function onTrademarkPick(uploadFile: { raw?: File }) {
  if (sampleImageBlocked.value) return
  const file = uploadFile?.raw
  if (!file) return
  if (file.size > 2 * 1024 * 1024) { ElMessage.warning('商标图样请小于 2MB'); return }
  const reader = new FileReader()
  reader.onload = () => { s.trademarkImage = String(reader.result || '') }
  reader.readAsDataURL(file)
}
// 派生报告沿用原样品编号；报告后缀不属于实物样品。
const sampleAutoNo = computed(() => {
  if (isChange.value && s.sampleNo) return s.sampleNo
  if (activeSavedReportNo.value && s.sampleNo) return s.sampleNo
  if (s.reportCategory !== '普通') {
    return sourceSample.value?.reportNo === s.baseReportNo ? sourceSample.value.sampleNo : ''
  }
  return reportPrefix.value ? `${today.slice(0, 4)}${s.schemeCode || 'R'}-****` : ''
})

// 检测依据/判定标准（检测标准基础信息库远程搜索，含一单一库标记）
const stdOptions = ref<StdLibHit[]>([])
const stdLoading = ref(false)
let stdSearchRequestSeq = 0
const capabilityOptions = ref<CapabilityItemRow[]>([])
const capabilityLoading = ref(false)
const capabilityDialogOpen = ref(false)
const capabilityError = ref('')
const capabilityCurrentRows = ref<CapabilityItemRow[]>([])
const capabilityCheckedContext = ref('')
const availableCapabilityIds = ref<number[]>([])
const unavailableCapabilityIds = computed(() => capabilityCheckedContext.value === selectionContext()
  ? s.capabilityEntryIds.filter(id => !availableCapabilityIds.value.includes(id)) : [])
const unavailableCapabilityLabels = computed(() => selectedCapabilityLabels.value
  .filter(row => unavailableCapabilityIds.value.includes(row.id)).map(row => row.label))
const selectedCapabilityLabels = computed(() => {
  const rows = new Map([...s.capabilitySnapshots, ...capabilityOptions.value].map(row => [row.id, row]))
  return s.capabilityEntryIds.map(id => {
    const row = rows.get(id)
    return { id, label: row ? `${row.itemName}（${row.standardCode}）` : `历史已选参数 ${id}` }
  })
})
const selectedTestItemOrder = computed(() => reconcileTestItemOrder(s.testItemOrder, s.capabilityEntryIds, s.manualCapabilityItems))
const selectedTestItemRows = computed(() => testItemRows(selectedTestItemOrder.value, [...s.capabilitySnapshots, ...capabilityOptions.value]))
const commissionBasisNames = computed(() => Object.fromEntries(selectedBasisCodes().map(code => [code, selectedBasisRow(code)?.name || s.standardNames[code] || ''])))
const commissionBasisRecords = computed(() => selectedBasisRecords())
const commissionBasisText = computed(() => standardRecordPreview(commissionBasisRecords.value, true, s.basisTitleStyles, 'none', s.basisSeparator))
const commissionItemsText = computed(() => selectedTestItemRows.value.length
  ? selectedTestItemRows.value.map(row => row.label).join(s.itemsSeparator)
  : s.projectList.join(s.itemsSeparator))
const capabilityTotal = ref(0)
const capabilityLocations = ref<string[]>([])
const capabilityCatalogSelections = ref<CapabilityItemRow[]>([])
const catalogLoading = ref(false), catalogError = ref('')
let catalogSeq = 0, catalogController: AbortController | undefined
let catalogQuery = { keyword: '', locationFilter: '', accreditationFilter: '', page: 1, size: 20, selectedStandardsOnly: true }
const manualLocationOptions = ref<string[]>([]), manualLocationsLoading = ref(false), manualLocationsError = ref('')
let locationsController: AbortController | undefined
async function loadManualLocations() {
  locationsController?.abort()
  const controller = new AbortController(); locationsController = controller
  manualLocationsLoading.value = true; manualLocationsError.value = ''
  const timeout = setTimeout(() => controller.abort(), 12000)
  try { const rows = await fetchTestingLocations(controller.signal); if (controller === locationsController) manualLocationOptions.value = rows }
  catch { if (controller === locationsController) manualLocationsError.value = '数据库地点读取失败，请重试。' }
  finally { clearTimeout(timeout); if (controller === locationsController) manualLocationsLoading.value = false }
}
let catalogHydrated = false
function openCapabilityDialog() {
  if (readOnly.value) return
  catalogHydrated = false
  capabilityCatalogSelections.value = []
  capabilityCurrentRows.value = []
  capabilityTotal.value = 0
  capabilityLocations.value = []
  capabilityDialogOpen.value = true
  void loadManualLocations()
}
async function loadCapabilityCatalog(query = catalogQuery) {
  catalogQuery = query
  catalogController?.abort()
  const controller = new AbortController()
  catalogController = controller
  const requestSeq = ++catalogSeq, context = selectionContext()
  const current = () => requestSeq === catalogSeq && context === selectionContext() && capabilityDialogOpen.value
  catalogLoading.value = true
  catalogError.value = ''
  const timeout = setTimeout(() => controller.abort(), 15000)
  const scope = { allStandards: true, department: s.testDept }
  try {
    const [result, selected] = await Promise.all([
      fetchCapabilityPage({ ...scope, keyword: query.keyword, page: query.page, size: query.size,
        locationFilter: query.locationFilter, accreditationFilter: query.accreditationFilter, includeLocations: true,
        standardCodes: s.testBases, standardItemIds: [...s.standardItemIds] }, controller.signal),
      !catalogHydrated && s.capabilityEntryIds.length ? fetchCapabilityItems({ ...scope, ids: s.capabilityEntryIds, standardCodes: s.testBases, standardItemIds: [...s.standardItemIds] }, controller.signal) : Promise.resolve([]),
    ])
    if (!current()) return
    catalogHydrated = true
    capabilityCurrentRows.value = result.rows
    capabilityTotal.value = result.total
    capabilityLocations.value = result.locations || []
    capabilityCatalogSelections.value = [...new Map([...capabilityCatalogSelections.value, ...selected, ...result.rows].map(row => [row.id, row])).values()]
    capabilityOptions.value = [...new Map([...capabilityOptions.value, ...selected, ...result.rows].map(row => [row.id, row])).values()]
  } catch {
    if (current()) { capabilityCurrentRows.value = []; catalogError.value = '库内项目读取失败或超时，请重新加载；已选项目保留。' }
  } finally { clearTimeout(timeout); if (requestSeq === catalogSeq) catalogLoading.value = false }
}
onUnmounted(() => { ++catalogSeq; catalogController?.abort(); locationsController?.abort() })
watch(capabilityDialogOpen, open => { if (!open) { ++catalogSeq; catalogController?.abort(); catalogLoading.value = false } })
let capabilityConfirmSeq = 0
watch(capabilityDialogOpen, () => { capabilityConfirmSeq++ })
async function confirmCapabilitySelection(ids: number[], manual = s.manualCapabilityItems, order: TestItemRef[] = [], locations: ManualParameterLocations = {}) {
  if (readOnly.value) return
  const context = selectionContext(), request = ++capabilityConfirmSeq
  // Parameter source text is descriptive; it must never add another standard.
  const nextBases = [...selectedBasisCodes()]
  try { await hydrateStandardOptions(nextBases) }
  catch { ElMessage.error('对应检测依据读取失败，请重新选择项目'); return }
  if (request !== capabilityConfirmSeq || context !== selectionContext()) return
  if (nextBases.some(code => !stdOptions.value.some(row => row.code === code))) { ElMessage.error('部分检测依据无法读取，请重新选择项目'); return }
  const judgeFollows = judgmentFollows(s.testBases)
  s.testBases = nextBases
  syncBasisFields()
  if (judgeFollows) followTestingBases()
  basisBeforeChange.value = [...s.testBases]
  s.capabilityEntryIds = [...ids]
  availableCapabilityIds.value = [...ids]
  capabilityCheckedContext.value = selectionContext()
  capabilityError.value = ''
  s.manualCapabilityItems = [...manual]
  s.manualParameterLocations = locations
  s.testItemOrder = reconcileTestItemOrder(order, ids, manual)
  onCapabilityChange(ids)
  capabilityDialogOpen.value = false
}
function reorderBases(codes: string[]) {
  if (readOnly.value) return
  const follows = judgmentFollows(s.testBases)
  s.testBases = codes
  syncBasisFields()
  basisBeforeChange.value = [...codes]
  if (follows) followTestingBases()
}
function reorderTestItems(keys: string[]) {
  if (readOnly.value) return
  const byKey = new Map(selectedTestItemOrder.value.map(item => [testItemKey(item), item]))
  s.testItemOrder = keys.map(key => byKey.get(key)!).filter(Boolean)
  s.capabilityEntryIds = s.testItemOrder.flatMap(item => item.kind === 'library' ? [item.id] : [])
  s.manualCapabilityItems = s.testItemOrder.flatMap(item => item.kind === 'manual' ? [item.name] : [])
  onCapabilityChange(s.capabilityEntryIds)
}
function removeTestItem(key: string) { reorderTestItems(selectedTestItemOrder.value.map(testItemKey).filter(item => item !== key)) }
const capabilityLoadedBasis = ref('')
function splitBasisValues(value: unknown): string[] {
  const source = Array.isArray(value) ? value : String(value || '').split(/[、；;\n]+/)
  return [...new Set(source.map((item) => String(item || '').trim()).filter(Boolean))]
}
function selectedBasisCodes(): string[] {
  // testBases is the editable source of truth after the form has been hydrated.
  // Falling back to the legacy string here would restore the last removed item
  // before syncBasisFields() has a chance to clear testBasis.
  return splitBasisValues(s.testBases)
}
function basisKey(): string {
  return JSON.stringify([selectedBasisCodes(), s.standardItemIds])
}
// Codes identify editions; IDs distinguish the individual language/name record.
function selectedBasisRow(code: string, ids = s.standardItemIds): StdLibHit | undefined {
  const rows = stdOptions.value.filter(row => row.code === code)
  return rows.find(row => ids.includes(Number(row.id)))
    || (!ids.some(id => !stdOptions.value.some(row => Number(row.id) === id)) && rows.length === 1 ? rows[0] : undefined)
}
function selectedBasisRecords(codes = selectedBasisCodes(), ids = s.standardItemIds): StandardDisplayRecord[] {
  const rows: StandardDisplayRecord[] = []
  for (const id of [...new Set(ids)]) {
    const row = stdOptions.value.find(row => Number(row.id) === id) || s.standardRecords.find(row => row.id === id)
    if (row && codes.includes(row.code)) rows.push({id, key: `id:${id}`, code: row.code, name: row.name || ''})
    else if ((!row || row.code === `历史标准 ${id}`) && codes.length) rows.push({id, key: `id:${id}`, code: codes.length === 1 ? codes[0] : `历史标准 ${id}`, name: s.standardNames[`id:${id}`] || (codes.length === 1 ? s.standardNames[codes[0]] || '' : '')})
  }
  for (const code of codes) {
    if (rows.some(row => row.code === code)) continue
    const row = !ids.length ? selectedBasisRow(code, []) : undefined
    rows.push({id: row?.id, key: row?.id ? `id:${row.id}` : `code:${code}`, code, name: row?.name || s.standardNames[code] || ''})
  }
  return rows
}
function selectedBasisIds(): string[] {
  return selectedBasisRecords().map(row => row.id ? String(row.id) : `code:${row.code}`)
}
async function onBasisIdsChange(ids: string[]) {
  const rows = ids.map(id => stdOptions.value.find(row => String(row.id) === id)).filter((row): row is StdLibHit => !!row)
  if (rows.length !== ids.length) throw new Error('部分标准记录未载入，请重新选择对应名称版本')
  await onBasesChange(splitBasisValues(rows.map(row => row.code)), [...new Set(rows.map(row => Number(row.id)))])
}
function syncBasisFields() {
  s.testBases = selectedBasisCodes()
  s.testBasis = s.testBases.join('；')
  const records = selectedBasisRecords()
  s.standardItemIds = records.flatMap(row => row.id ? [row.id] : [])
  s.standardRecords = records.filter(row => row.id)
  const selectedRows = s.standardItemIds.map(id => stdOptions.value.find(row => Number(row.id) === id)).filter((row): row is StdLibHit => !!row)
  s.standardNames = Object.fromEntries([
    ...records.map(row => [row.key, row.name]),
    ...s.testBases.map(code => [code, records.filter(row => row.code === code).length === 1 ? records.find(row => row.code === code)?.name || '' : '']),
  ])
  s.standardItemId = s.standardItemIds[0] || 0
  s.testBasisSingle = Boolean(s.testBases.length)
    && selectedRows.length === records.length
    && selectedRows.every((row) => row.singleList)
}
function normalizeSampleBasisState() {
  // Older records may only contain the legacy single string. Import that value
  // once during hydration, then keep the multiple selection authoritative so
  // the user can temporarily clear all items before choosing a replacement.
  s.testBases = splitBasisValues(s.testBases.length ? s.testBases : s.testBasis)
  syncBasisFields()
}
const capabilityUnavailable = computed(() => (
  selectedBasisCodes().length > 0
  && !capabilityLoading.value
  && capabilityLoadedBasis.value === basisKey()
  && Boolean(capabilityError.value)
))
const capabilityPlaceholder = computed(() => {
  if (!selectedBasisCodes().length) return '请先选择一个或多个检测依据标准'
  if (capabilityLoading.value) return '正在读取 CNAS/CMA 能力附表'
  return '打开选择窗口后按需搜索授权项目'
})
const basisBeforeChange = ref<string[]>([])
const basisDialogOpen = ref(false)
const basisError = ref('')
const basisKeyword = ref('')
const basisScopeFilter = ref<'all' | 'cnas' | 'cma' | 'single'>('all')
const basisCapabilityOnly = ref(false)
const basisSelectedOnly = ref(false)
const basisDraftCodes = ref<string[]>([])
const basisDraftItemIds = ref<number[]>([])
const basisPageRows = ref<StdLibHit[]>([])
const basisPage = ref(1)
const basisPageSize = ref(50)
const basisTotal = ref(0)
let basisSearchRequestSeq = 0
let capabilityRequestSeq = 0
let sampleContextEpoch = 0
let basisSelectionRevision = 0
function selectionContext() {
  return JSON.stringify([sampleContextEpoch, props.changeReportNo, s.testDept, selectedBasisCodes(), basisSelectionRevision])
}
const basisDraftRecords = computed(() => selectedBasisRecords(basisDraftCodes.value, basisDraftItemIds.value))
const basisSelectedRows = computed(() => {
  const keyword = basisKeyword.value.trim().toLowerCase()
  return basisDraftRecords.value.map(record => stdOptions.value.find(row => row.id === record.id)
    || { ...record, cnas: false, cma: false, singleList: false, authKind: '', status: '现行', useDepts: [], controlledNo: '' } as StdLibHit)
    .filter(row => (!keyword || `${row.code} ${row.name}`.toLowerCase().includes(keyword))
      && (basisScopeFilter.value === 'all' || (basisScopeFilter.value === 'cnas' ? row.cnas
        : basisScopeFilter.value === 'cma' ? row.cma : row.singleList))
      && (!basisCapabilityOnly.value || !!row.capabilityTypes?.length))
})
const basisVisibleTotal = computed(() => basisSelectedOnly.value ? basisSelectedRows.value.length : basisTotal.value)
const basisDialogRows = computed(() => basisSelectedOnly.value
  ? basisSelectedRows.value.slice((basisPage.value - 1) * basisPageSize.value, basisPage.value * basisPageSize.value)
  : basisPageRows.value)
watch(basisVisibleTotal, total => { basisPage.value = Math.min(basisPage.value, Math.max(1, Math.ceil(total / basisPageSize.value))) })
function mergeStandardOptions(rows: StdLibHit[]) {
  const merged = new Map<string, StdLibHit>()
  for (const row of [...stdOptions.value, ...rows]) merged.set(row.id ? `id:${row.id}` : `code:${row.code}`, row)
  stdOptions.value = [...merged.values()]
}
async function searchStd(kw: string, capabilityOnly = false) {
  const requestSeq = ++stdSearchRequestSeq
  const context = selectionContext()
  const keyword = String(kw || '').trim()
  stdLoading.value = true
  try {
    const options = await searchStdLib(keyword, s.testDept, {
      capabilityOnly,
    })
    if (requestSeq === stdSearchRequestSeq && context === selectionContext()) {
      const selected = new Set(selectedBasisCodes())
      const retained = stdOptions.value.filter((row) => selected.has(row.code))
      stdOptions.value = [...new Map([...retained, ...options].map((row) => [row.id ? `id:${row.id}` : `code:${row.code}`, row])).values()]
    }
  } catch {
    if (requestSeq === stdSearchRequestSeq && context === selectionContext()) {
      stdOptions.value = []
    }
  } finally {
    if (requestSeq === stdSearchRequestSeq) {
      stdLoading.value = false
    }
  }
}
async function hydrateStandardOptions(codes: string[]) {
  const context = selectionContext()
  const missing = codes.filter((code) => !stdOptions.value.some((row) => row.code === code))
  const missingIds = s.standardItemIds.filter(id => !stdOptions.value.some(row => Number(row.id) === id))
  if (!missing.length && !missingIds.length) {
    syncBasisFields()
    syncTestLocationWithStandards()
    return
  }
  const requests = missing.map((code) => searchStdLib(code, s.testDept, {
  }).catch(() => []))
  if (missingIds.length) requests.push(searchStdLib('', s.testDept, { ids: missingIds, size: 200 }).catch(() => []))
  const rows = (await Promise.all(requests)).flat()
  if (context !== selectionContext()) return
  mergeStandardOptions(rows)
  syncBasisFields()
  syncTestLocationWithStandards()
}
function cmaScopeLabel(item: StdLibHit) {
  if (!item.cma) return '非CMA范围'
  return item.singleList ? 'CMA范围内' : 'CMA授权（非一单一库）'
}
function rememberBasis() { basisBeforeChange.value = [...selectedBasisCodes()] }
function basisDisplayLabel(code: string, ids = s.standardItemIds) {
  const row = selectedBasisRow(code, ids)
  return row?.name ? `${code} · ${row.name}` : code
}
function standardDocumentText(value: string | string[]) {
  const codes = splitBasisValues(value)
  return codes.map((code) => basisDisplayLabel(code).replace(' · ', ' ')).join('；')
}
function digitsOnly(value: string) { return String(value || '').replace(/\D/g, '') }
async function openBasisDialog() {
  if (readOnly.value) return
  rememberBasis()
  basisDraftCodes.value = [...selectedBasisCodes()]
  basisDraftItemIds.value = [...s.standardItemIds]
  basisKeyword.value = ''
  basisScopeFilter.value = 'all'
  basisCapabilityOnly.value = false
  basisSelectedOnly.value = false
  basisPage.value = 1
  basisDialogOpen.value = true
  await hydrateStandardOptions(basisDraftCodes.value)
  basisDraftItemIds.value = [...s.standardItemIds]
  await queryBasisStandards()
}
async function queryBasisStandards() {
  const requestSeq = ++basisSearchRequestSeq
  basisError.value = ''
  if (basisSelectedOnly.value) { stdLoading.value = false; return }
  const context = JSON.stringify([selectionContext(), basisKeyword.value, basisScopeFilter.value, basisCapabilityOnly.value, basisDialogOpen.value])
  const current = () => requestSeq === basisSearchRequestSeq && context === JSON.stringify([selectionContext(), basisKeyword.value, basisScopeFilter.value, basisCapabilityOnly.value, basisDialogOpen.value])
  stdLoading.value = true
  try {
    const result = await searchStdLibPage(basisKeyword.value.trim(), s.testDept, {
      capabilityOnly: basisCapabilityOnly.value,
      scopeFilter: basisScopeFilter.value,
      page: basisPage.value,
      size: basisPageSize.value,
    })
    if (!current()) return
    basisPageRows.value = result.rows
    basisTotal.value = result.total
    basisPage.value = result.page
    mergeStandardOptions(result.rows)
  } catch {
    if (current()) {
      basisPageRows.value = []
      basisTotal.value = 0
      basisError.value = '检测依据读取失败，请点击搜索重试。已选标准已保留。'
    }
  } finally {
    if (current()) stdLoading.value = false
  }
}
async function runBasisSearchFromStart() {
  basisPage.value = 1
  await queryBasisStandards()
}
function toggleBasisDraft(row: Pick<StdLibHit, 'id' | 'code' | 'name'>, selected: boolean) {
  if ('authKind' in row) mergeStandardOptions([row as StdLibHit])
  if (!row.id) return
  if (selected) {
    basisDraftItemIds.value = [...new Set([...basisDraftItemIds.value, row.id])]
    basisDraftCodes.value = [...new Set([...basisDraftCodes.value, row.code])]
  } else {
    basisDraftItemIds.value = basisDraftItemIds.value.filter(id => id !== row.id)
    if (!basisDraftItemIds.value.some(id => stdOptions.value.some(item => item.id === id && item.code === row.code)
      || s.standardRecords.some(item => item.id === id && item.code === row.code))) {
      basisDraftCodes.value = basisDraftCodes.value.filter(code => code !== row.code)
    }
  }
}
function toggleBasisDraftByCode(code: string, selected: boolean) {
  const next = new Set(basisDraftCodes.value)
  if (selected) next.add(code)
  else {
    next.delete(code)
    basisDraftItemIds.value = basisDraftItemIds.value.filter(id => !stdOptions.value.some(row => row.id === id && row.code === code))
  }
  basisDraftCodes.value = [...next]
}
function reorderBasisDraft(keys: string[]) {
  const rows = keys.map(key => basisDraftRecords.value.find(row => row.key === key)).filter((row): row is StandardDisplayRecord => !!row)
  basisDraftItemIds.value = rows.flatMap(row => row.id ? [row.id] : [])
  basisDraftCodes.value = splitBasisValues(rows.map(row => row.code))
}
function removeBasisDraft(key: string) {
  const row = basisDraftRecords.value.find(row => row.key === key)
  if (row?.id) toggleBasisDraft(row, false)
  else if (row) toggleBasisDraftByCode(row.code, false)
}
async function confirmBasisSelection() {
  const requested = [...basisDraftCodes.value]
  const requestedIds = [...basisDraftItemIds.value]
  basisBeforeChange.value = [...selectedBasisCodes()]
  await onBasesChange(requested, [...basisDraftItemIds.value])
  basisDraftCodes.value = [...selectedBasisCodes()]
  basisDraftItemIds.value = [...s.standardItemIds]
  if (JSON.stringify(requestedIds) === JSON.stringify(basisDraftItemIds.value) && requested.length === basisDraftCodes.value.length && requested.every((code, index) => code === basisDraftCodes.value[index])) {
    basisDialogOpen.value = false
  }
}
async function removeBasis(code: string) {
  rememberBasis()
  await onBasesChange(selectedBasisCodes().filter((item) => item !== code))
}
const capabilitySite = capabilitySiteForAddress
const selectedStandardSiteCodes = computed(() => {
  const codes = selectedBasisCodes()
  if (!codes.length) return []
  const rows = selectedBasisRecords().map(record => stdOptions.value.find(row => row.id === record.id))
  if (rows.some((row) => !row)) return []
  return commonCapabilitySites(rows.map((row) => row?.sites || []))
})
const testLocationOptions = computed(() => fullAddressesForSites(selectedStandardSiteCodes.value))
function syncTestLocationWithStandards() {
  if (s.locationWorkflowVersion === 1) { syncParameterLocations(); return }
  if (s.testLocation) return // Opening a historical sample never recalculates its saved address.
  const options = testLocationOptions.value
  if (!selectedBasisCodes().length || !options.length) {
    s.testLocation = ''
    return
  }
  const currentSite = capabilitySite(s.testLocation)
  if (currentSite && selectedStandardSiteCodes.value.includes(currentSite)) {
    if (options.includes(s.testLocation)) return
    const sameSiteOptions = CAPABILITY_SITE_FULL_ADDRESSES[currentSite] || []
    if (sameSiteOptions.length === 1) {
      s.testLocation = sameSiteOptions[0]
      return
    }
  }
  s.testLocation = options.length === 1 ? options[0] : ''
}
const parameterLocationError = ref('')
function syncParameterLocations() {
  if (s.locationWorkflowVersion !== 1) return
  parameterLocationError.value = ''
  // Historical addresses are display facts, not proof of current authorization.
  // Keep them intact until the unavailable choices are explicitly resolved.
  if (unavailableCapabilityIds.value.length || capabilityError.value) return
  const byId = new Map([...s.capabilitySnapshots, ...capabilityOptions.value].map((row) => [row.id, row]))
  const rows = s.capabilityEntryIds.map((id) => byId.get(id)).filter((row): row is CapabilityItemRow => Boolean(row))
  try {
    if (rows.length !== s.capabilityEntryIds.length) throw new Error('所选参数未完整读取')
    s.actualTestLocations = actualParameterAddresses(rows, s)
    s.testLocation = s.actualTestLocations.join('；')
  } catch (error) {
    parameterLocationError.value = error instanceof Error ? error.message : '检测地点无法汇总'
    s.actualTestLocations = actualParameterAddresses(rows.filter(row => Boolean(row.address)), s, false)
    s.testLocation = s.actualTestLocations.join('；')
  }
}
function onManualCapabilityChange() {
  s.locationWorkflowVersion = 1
  syncParameterLocations()
}
async function onOnsiteTestingChange() {
  // Address mode is independent of selected standards, parameters and ordering.
  s.locationWorkflowVersion = 1
  syncParameterLocations()
}
async function loadCapabilityItems(preserveSavedLocation = false) {
  const requestSeq = ++capabilityRequestSeq
  const context = selectionContext()
  const current = () => requestSeq === capabilityRequestSeq && context === selectionContext()
  const standards = selectedBasisCodes()
  if (!standards.length) {
    capabilityOptions.value = []
    capabilityCurrentRows.value = []
    availableCapabilityIds.value = []
    capabilityCheckedContext.value = context
    capabilityError.value = ''
    capabilityLoadedBasis.value = ''
    capabilityLoading.value = false
    return
  }
  capabilityLoading.value = true
  capabilityError.value = ''
  try {
    await hydrateStandardOptions(standards)
    if (!current()) return
    syncBasisFields()
    const options = s.capabilityEntryIds.length ? await fetchCapabilityItems({
      allStandards: true, ids: s.capabilityEntryIds, standardCodes: standards, standardItemIds: [...s.standardItemIds],
      department: s.testDept,
    }) : []
    if (!current()) return
    capabilityCurrentRows.value = options
    const selected = new Set(s.capabilityEntryIds)
    const history = s.capabilitySnapshots.filter((item) => selected.has(item.id))
    capabilityOptions.value = [...new Map([...history, ...options].map((item) => [item.id, item])).values()]
    capabilityLoadedBasis.value = basisKey()
    availableCapabilityIds.value = options.map(item => item.id)
    capabilityCheckedContext.value = context
    if (!preserveSavedLocation) syncParameterLocations()

  } catch {
    if (!current()) return
    capabilityCurrentRows.value = []
    capabilityError.value = '授权能力项目读取失败，请关闭后重试；不会将部分结果当作全部项目'
    capabilityOptions.value = []
    capabilityLoadedBasis.value = basisKey()
    ElMessage.error('CNAS/CMA 能力项目读取失败，请稍后重试')
  } finally {
    if (requestSeq === capabilityRequestSeq) capabilityLoading.value = false
  }
}
function onCapabilityChange(ids: number[]) {
  s.locationWorkflowVersion = 1
  s.testItemOrder = reconcileTestItemOrder(s.testItemOrder, ids, s.manualCapabilityItems)
  s.projectList = testItemRows(s.testItemOrder, [...s.capabilitySnapshots, ...capabilityOptions.value]).map(row => row.label)
  s.project = s.projectList.join('、')
  syncParameterLocations()
  sampleConfigErrors.value = []
}
// Only an empty or still-auto-filled judgment follows testing bases; preserve custom input.
let basisChangeRequest = 0
async function onBasesChange(values: string[], recordIds?: number[]) {
  const request = ++basisChangeRequest, context = selectionContext()
  const current = () => request === basisChangeRequest && context === selectionContext()
  const next = splitBasisValues(values)
  const previous = [...basisBeforeChange.value]
  const judgmentFollowsBasis = judgmentFollows(previous)
  const nextIds = recordIds ?? s.standardItemIds.filter(id => {
    const row = stdOptions.value.find(item => item.id === id) || s.standardRecords.find(item => item.id === id)
    return row ? next.includes(row.code) : next.length > 0
  })
  const hasRemoval = s.standardItemIds.some(id => !nextIds.includes(id)) || previous.some(code => !next.includes(code))
  let removedParameterIds = new Set<number>()
  if (hasRemoval && s.capabilityEntryIds.length) {
    try {
      const retained = nextIds.length ? await fetchCapabilityItems({allStandards: true, department: s.testDept,
        ids: s.capabilityEntryIds, standardCodes: next, standardItemIds: nextIds}) : []
      if (!current()) return
      const keep = new Set(retained.map(row => row.id))
      removedParameterIds = new Set(s.capabilityEntryIds.filter(id => !keep.has(id)))
    } catch { ElMessage.error('参数归属读取失败，已保留原标准和参数，请重试'); return }
  }
  if (removedParameterIds.size) {
    try {
      await ElMessageBox.confirm(
        '移除或切换检测标准记录后，需要清除该记录对应的已选参数并重新选择。其他标准和库外项目保留。',
        '确认更换检测标准',
        { type: 'warning', confirmButtonText: '移除并清除', cancelButtonText: '取消' },
      )
      if (!current()) return
      s.capabilityEntryIds = s.capabilityEntryIds.filter((id) => !removedParameterIds.has(id))
    } catch {
      if (!current()) return
      s.testBases = previous
      syncBasisFields()
      return
    }
  }
  if (!current()) return
  s.standardItemIds = [...nextIds]; basisSelectionRevision += 1
  s.testBases = next
  s.locationWorkflowVersion = 1
  syncBasisFields()
  syncTestLocationWithStandards()
  if (judgmentFollowsBasis) followTestingBases()
  sampleConfigErrors.value = []
  await loadCapabilityItems()
  onCapabilityChange(s.capabilityEntryIds)
  basisBeforeChange.value = [...next]
}
// CMA 盖章但检测依据不在一单一库 → 提示
const cmaScopeWarn = computed(() => s.seal.includes('CMA') && !!s.testBasis && !s.testBasisSingle)
// 检测方案（按部门选，方案编号进报告号）
const schemeDialogOpen = ref(false)
const schemeKeyword = ref('')
const schemeTree = ref<SchemeNode[]>([])
const beginSchemeSearch = useSearchRequest(() => [schemeKeyword.value, props.modelValue, sampleContextEpoch])
async function loadSchemes() {
  const current = beginSchemeSearch()
  try { const rows = await fetchSchemes(schemeKeyword.value); if (current()) schemeTree.value = rows }
  catch (error) { if (current()) { schemeTree.value = []; ElMessage.error(error instanceof Error ? error.message : '检测方案加载失败，请重新查询') } }
}
function openSchemeDialog() {
  if (schemeLocked.value) {
    ElMessage.warning('样品号/报告号已生成，检测方案及编号类别不能更改')
    return
  }
  schemeKeyword.value = ''
  loadSchemes()
  schemeDialogOpen.value = true
}
async function pickScheme(sc: SchemeRow) {
  if (schemeLocked.value) {
    ElMessage.warning('样品号/报告号已生成，检测方案及编号类别不能更改')
    schemeDialogOpen.value = false
    return
  }
  s.schemeName = sc.name
  s.schemeCode = sc.numberCode || sc.code
  schemeDialogOpen.value = false
  const parameters = String(sc.detectionParameters || sc.project || '').trim()
  const parameterList = parameters
    .split(/[、,，;；\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  s.projectList = parameterList
  s.project = parameters
  s.testDept = sc.testDept || sc.dept || ''
  const previousCenter = s.centerPrefix
  s.centerPrefix = sc.centerPrefix || s.centerPrefix
  s.testCategory = sc.testCategory || s.testCategory
  s.reportType = sc.reportType || sc.reportFormat || s.reportType
  s.sampleAmount = sc.sampleAmount || s.sampleAmount
  s.appearance = sc.sampleStatus || s.appearance
  s.testLocation = sc.testLocation || sc.location || s.testLocation
  s.testRoom = sc.testRoom || ''
  s.testBases = splitBasisValues(sc.testBasis || '')
  syncBasisFields()
  s.judgmentEntries = undefined
  s.standardJudge = sc.standardJudge || sc.testBasis || ''
  s.deadline = sc.defaultCycle || s.deadline
  if (s.centerPrefix !== previousCenter) s.seal = sealByCenter(s.centerPrefix)
  else if (!['NCSA', 'NCAS'].includes(s.centerPrefix)) s.seal = sc.sealRequirement || s.seal
  sampleConfigErrors.value = []
  if (s.testBases.length) await hydrateStandardOptions(s.testBases)
  syncBasisFields()
  s.capabilityEntryIds = []
  await loadCapabilityItems()
  const autoFilled = [
    sc.reportTitle || sc.centerPrefix,
    sc.testCategory,
    sc.reportType || sc.reportFormat,
    sc.testDept || sc.dept,
    parameters,
    sc.sampleAmount,
    sc.sampleStatus,
    sc.testLocation || sc.location,
  ].filter(Boolean).length
  ElMessage.success(`检测方案已选择，并自动填写 ${autoFilled} 项方案参数`)
}

const previewing = ref(false)
const entrustPreviewMessage = ref('正在准备委托单，后台生成期间可以关闭窗口')
const coverPreviewOpen = ref(false)
const coverPdfUrl = ref('')
let reusableEntrust: { file: EntrustPreviewFile; fingerprint: string; template: BusinessFormTemplateKind; language: EntrustLanguage; account: string | undefined } | undefined
let entrustDocumentRevision = 0
function invalidateEntrustDocument() {
  ++entrustDocumentRevision
  if (coverPdfUrl.value) URL.revokeObjectURL(coverPdfUrl.value)
  coverPdfUrl.value = ''
  reusableEntrust = undefined
}
watch(() => session.account, invalidateEntrustDocument)
onUnmounted(invalidateEntrustDocument)
const previewTemplateKind = ref<BusinessFormTemplateKind>('product')
const previewTemplateChosen = ref(false)
const entrustLanguages = [
  { label: '中文', value: 'CN' },
  { label: '英文', value: 'EN' },
  { label: '中英文', value: 'BI' },
] as const
type EntrustLanguage = (typeof entrustLanguages)[number]['value']
const previewLanguage = ref<EntrustLanguage>('CN')
const entrustExportOpen = ref(false)
const exportTemplateKind = ref<BusinessFormTemplateKind>('product')
const exportLanguage = ref<EntrustLanguage>('CN')
function openEntrustExport() {
  if (!props.modelValue || previewing.value || submitting.value || sampleFormLoading.value || sampleFormError.value || !sampleEntrustNo.value) return
  exportTemplateKind.value = previewTemplateChosen.value ? previewTemplateKind.value : inferredEntrustTemplateKind()
  exportLanguage.value = previewLanguage.value
  entrustExportOpen.value = true
}
async function confirmEntrustExport() {
  if (!entrustExportOpen.value || !props.modelValue || previewing.value || submitting.value) return
  if (!BUSINESS_FORM_TEMPLATE_OPTIONS.some(option => option.value === exportTemplateKind.value)) return
  previewTemplateKind.value = exportTemplateKind.value
  previewLanguage.value = exportLanguage.value
  previewTemplateChosen.value = true
  if (await downloadEntrustPreviewPdf()) entrustExportOpen.value = false
}
function inferredEntrustTemplateKind(): BusinessFormTemplateKind {
  const item = currentSampleItem()
  const projectType = `${item.entrustSnapshot.projectType || ''} ${item.reportType || ''}`
  return projectType.includes('工程') ? 'engineering' : 'product'
}
async function openEntrustPreview() {
  if (!previewTemplateChosen.value) previewTemplateKind.value = inferredEntrustTemplateKind()
  coverPreviewOpen.value = true
  await onPreviewEntrust()
}
async function onPreviewTemplateChange() {
  previewTemplateChosen.value = true
  await onPreviewEntrust()
}
async function onPreviewEntrust() {
  if (judgmentInput.value?.hasPending) {
    ElMessage.warning('请先添加或取消尚未保存的判定标准，再预览委托单')
    return false
  }
  if (sampleImageBlocked.value) {
    ElMessage.warning('原商标图样尚未加载完成，暂不能预览或导出，请等待或重试图样')
    return false
  }
  if (submitting.value) {
    ElMessage.warning('正在保存，请保存成功后再导出委托单')
    return false
  }
  if (sampleFormLoading.value || sampleFormError.value) {
    ElMessage.warning('样品资料尚未加载完成，不能预览或导出')
    return false
  }
  if (previewing.value) return false
  if (!sampleEntrustNo.value) return ElMessage.warning('请先选择委托单')
  const epoch = sampleFormEpoch
  const documentRevision = entrustDocumentRevision
  const reportNo = props.changeReportNo
  previewing.value = true
  try {
    const item = currentSampleItem()
    const fingerprint = JSON.stringify(item)
    const templateKind = previewTemplateKind.value
    const language = previewLanguage.value
    const reusable = reusableEntrust?.fingerprint === fingerprint
      && reusableEntrust.template === templateKind && reusableEntrust.account === session.account
      && reusableEntrust.language === language
      && reusableEntrust.file.url === coverPdfUrl.value ? reusableEntrust.file : undefined
    if (!reusable && coverPdfUrl.value) {
      URL.revokeObjectURL(coverPdfUrl.value)
      coverPdfUrl.value = ''
      reusableEntrust = undefined
    }
    const detail = buildDetail(item)
    const res = await previewSampleEntrust({
      entrustSnapshot: item.entrustSnapshot,
      detail,
      rawSample: detail.rawSample,
      reportNo: effectiveReportNo.value,
      sampleNo: item.sampleNo,
      project: item.project,
      department: item.testDept,
      owner: item.entrustSnapshot.owner,
      deadline: item.deadline,
      erpProjectNo: item.entrustSnapshot.info?.erpProjectNo || '',
      outputLanguage: language,
    }, templateKind, () => epoch === sampleFormEpoch && documentRevision === entrustDocumentRevision && props.modelValue,
    message => { entrustPreviewMessage.value = message }, reusable)
    if (epoch !== sampleFormEpoch || documentRevision !== entrustDocumentRevision || reportNo !== props.changeReportNo || !props.modelValue) {
      URL.revokeObjectURL(res.url)
      return false
    }
    if (fingerprint !== JSON.stringify(currentSampleItem()) || templateKind !== previewTemplateKind.value || language !== previewLanguage.value) {
      URL.revokeObjectURL(res.url)
      invalidateEntrustDocument()
      ElMessage.warning('表单或模板已变化，请重新生成委托单')
      return false
    }
    if (coverPdfUrl.value && coverPdfUrl.value !== res.url) URL.revokeObjectURL(coverPdfUrl.value)
    coverPdfUrl.value = res.url
    reusableEntrust = { file: res, fingerprint, template: templateKind, language, account: session.account }
    return true
  } catch (e) {
    invalidateEntrustDocument()
    ElMessage.error(e instanceof Error ? e.message : '委托单预览失败')
    return false
  } finally {
    previewing.value = false
  }
}
async function validateEntrustPreviewDownload() {
  const previousUrl = coverPdfUrl.value
  if (!await onPreviewEntrust()) return false
  if (previousUrl !== coverPdfUrl.value) {
    ElMessage.warning('委托单已更新，请确认预览并重新选择下载页码')
    return false
  }
  return true
}
async function downloadEntrustPreviewPdf() {
  // Always validate the latest snapshot with the server. Only a confirmed
  // unchanged result can reuse the existing file; failure never exports it.
  if (!previewTemplateChosen.value) previewTemplateKind.value = inferredEntrustTemplateKind()
  if (!await onPreviewEntrust() || !coverPdfUrl.value) return false
  const link = document.createElement('a')
  link.href = coverPdfUrl.value
  const templateLabel = BUSINESS_FORM_TEMPLATE_OPTIONS.find(option => option.value === previewTemplateKind.value)?.label || previewTemplateKind.value
  link.download = `${s.sampleNo || sampleReportNo.value || 'sample'}-WT-${templateLabel}${previewLanguage.value === 'CN' ? '' : '-' + previewLanguage.value}.pdf`
  link.click()
  return true
}

// 已有表单复制：搜索保存过的委托/样品，一键复制到当前表单
const copyDialogOpen = ref(false)
const copyKeyword = ref('')
const copyEntrusts = ref<EntrustOrder[]>([])
const copySamples = ref<SampleCopyRow[]>([])
const copyLoading = ref(false)
const copyError = ref('')
const copyPage = ref(1)
const copyTotal = ref(0)
const beginCopySearch = useSearchRequest(() => [copyKeyword.value, copyPage.value, copyDialogOpen.value, props.modelValue, sampleFormEpoch])
async function loadCopySamples() {
  const current = beginCopySearch()
  copyLoading.value = true
  copyError.value = ''
  copySamples.value = []
  try {
    const result = await fetchSampleCopyPage(copyKeyword.value.trim(), copyPage.value)
    if (!current()) return
    copySamples.value = result.rows
    copyTotal.value = result.total
  } catch (error) {
    if (current()) { copyTotal.value = 0; copyError.value = error instanceof Error ? error.message : '读取已保存样品失败，请重试' }
  } finally { if (current()) copyLoading.value = false }
}
function changeCopyPage(page: number) { copyPage.value = page; void loadCopySamples() }
useLiveSearch(copyKeyword, () => { copyPage.value = 1; return loadCopySamples() }, () => copyDialogOpen.value && props.mode === 'samples')
watch(copyKeyword, () => {
  if (copyDialogOpen.value && props.mode === 'samples') { copySamples.value = []; copyLoading.value = true }
}, { flush: 'sync' })
watch(() => props.modelValue, open => { if (!open) copyDialogOpen.value = false })
async function openCopyDialog() {
  if (derivedSchemeLocked.value) return ElMessage.warning('派生报告请通过原报告选择继承信息')
  copyDialogOpen.value = false
  copyKeyword.value = ''
  copyPage.value = 1
  copyTotal.value = 0
  copyError.value = ''
  copyDialogOpen.value = true
  if (props.mode === 'samples') { await loadCopySamples(); return }
  copyLoading.value = true
  try {
    if (props.mode === 'entrust') copyEntrusts.value = await fetchEntrustList()
  } catch (error) { copyEntrusts.value = []; copySamples.value = []; copyError.value = error instanceof Error ? error.message : '委托单加载失败，请关闭后重试'; ElMessage.error(copyError.value) } finally { copyLoading.value = false }
}
const filteredCopyEntrusts = computed(() => {
  const kw = copyKeyword.value.trim().toLowerCase()
  const list = kw
    ? copyEntrusts.value.filter((e) => [e.entrustNo, e.client, e.projectName, e.contractNo].some((v) => (v || '').toLowerCase().includes(kw)))
    : copyEntrusts.value
  return list.slice(0, 50)
})
const filteredCopySamples = computed(() => {
  return copySamples.value
})

type SavedSummarySection = { title: string; fields: [string, string][] }

function savedEngineeringName(detail: { rawSample?: unknown; summary?: SavedSummarySection[] }) {
  const raw = detail.rawSample as Record<string, unknown> | undefined
  if (raw && Object.prototype.hasOwnProperty.call(raw, 'engineeringName')) return String(raw.engineeringName ?? '')
  const value = detail.summary?.find(section => section.title === '送样信息')?.fields.find(([label]) => label === '工程名称（幕墙）')?.[1] || ''
  return value === '—' ? '' : value
}

function cleanCopiedSampleText(value: unknown) {
  return String(value ?? '')
    .replace(/(?:\s*[-—_/:：]+\s*|\s+)添加样品\s*$/u, '')
    .trim()
}

function savedSchemeIdentity(row: Pick<SampleRow, 'reportNo' | 'sampleNo'>, summary: SavedSummarySection[]) {
  const schemeLabel = String(
    summary.find((item) => item.title === '实验信息')?.fields.find(([field]) => field === '检测方案')?.[1] ?? '',
  ).trim()
  const parsed = schemeLabel.match(/^(.*?)\s*[（(]\s*([A-Za-z0-9]+)\s*[）)]\s*$/u)
  return {
    name: parsed?.[1]?.trim() || (schemeLabel === '—' ? '' : schemeLabel),
    code: parsed?.[2] || row.sampleNo.match(/^\d{4}([A-Za-z0-9]+)-\d+$/i)?.[1] || '',
    centerPrefix: row.reportNo.match(/^([A-Za-z0-9]+)-/)?.[1] || '',
    label: schemeLabel === '—' ? '' : schemeLabel,
  }
}

function restoreLegacySampleForm(row: Pick<SampleRow, 'reportNo' | 'sampleNo'> & { project?: string }, summary: SavedSummarySection[]) {
  Object.assign(s, sampleBlank(), { locationWorkflowVersion: 0 })
  const find = (section: string, key: string) =>
    String(summary.find((item) => item.title === section)?.fields.find(([field]) => field === key)?.[1] ?? '')
  const value = (section: string, key: string) => {
    const result = find(section, key).trim()
    return result === '—' ? '' : result
  }
  const first = (section: string, ...keys: string[]) => {
    for (const key of keys) {
      const result = value(section, key)
      if (result) return result
    }
    return ''
  }

  // 旧样品没有 rawSample 时，从保存的各表单分区完整恢复可编辑字段。
  s.sampleName = cleanCopiedSampleText(first('送样信息', '样品名称', '样品/工程名称') || first('样品信息', '样品名称'))
  s.spec = cleanCopiedSampleText(first('送样信息', '规格型号'))
  s.manufacturer = cleanCopiedSampleText(first('送样信息', '生产厂家'))
  s.batch = first('送样信息', '代表批量')
  s.testDept = first('送样信息', '检测部门')
  s.testRoom = first('送样信息', '检测室')
  s.urgent = first('送样信息', '是否加急') || s.urgent
  s.deadline = first('送样信息', '检测期限') || s.deadline
  s.appearance = first('送样信息', '外观')
  s.nameplate = first('送样信息', '铭牌')
  s.trademark = first('送样信息', '商标')
  s.testLocation = first('送样信息', '检测地点')
  s.sampleAmount = first('送样信息', '样品数量')
  s.unit = first('送样信息', '数量单位', '单位')
  s.factoryNo = first('送样信息', '出厂编号')
  s.produceDate = first('送样信息', '生产日期')
  s.sendDate = first('送样信息', '送样日期') || s.sendDate
  s.reportType = first('送样信息', '报告类型') || s.reportType
  s.testCategory = first('送样信息', '检测类别', '检测类型') || s.testCategory

  s.remark = first('项目信息', '委托单备注')
  s.homepageRemark = first('项目信息', '报告首页备注')
  s.sampleUnit = first('抽样信息', '抽样单位')
  s.sampler = first('抽样信息', '抽样人')
  s.sampleTime = first('抽样信息', '抽样时间', '抽样日期')
  s.sampleQty = first('抽样信息', '抽样数量')
  s.entrustQty = first('抽样信息', '基数')
  s.inspectedUnit = first('抽样信息', '受检单位')
  s.taskSource = first('抽样信息', '任务来源')
  s.samplingLocation = first('抽样信息', '抽样地点')
  s.sampleArrivalDate = first('抽样信息', '样品到达日期')
  s.sampleGrade = first('抽样信息', '样品等级')
  s.sealStatus = first('抽样信息', '封样状态')
  s.sealChecker = first('抽样信息', '检查封样人员')

  s.stdPrice = first('结算信息', '标准价格')
  s.payStatus = first('结算信息', '缴费情况')
  s.payWay = first('结算信息', '支付方式')
  s.paid = first('结算信息', '已缴费')
  s.otherSettle = first('结算信息', '其他')
  const subText = first('子项目信息', '结算明细')
  s.subItems = parseLegacySubprojects(subText)

  s.sendOutTime = first('报告发送', '报告承诺时间(外部)')
  s.sendInTime = first('报告发送', '报告承诺时间(内部)')
  s.sampleHandle = first('报告发送', '样品处理方式')
  s.deliverWay = first('报告发送', '报告交付方式')
  s.mailAddr = first('报告发送', '邮寄地址')
  s.deliverStd = first('报告发送', '报告交付份数')
  s.reportForm = first('报告发送', '报告形式')
  s.fieldAgreement = first('报告发送', '现场检测时间约定')
  s.innerStdDate = first('报告发送', '约定检测日期')

  const project = first('实验信息', '检测项目') || row.project || ''
  s.project = project
  s.projectList = project.split('、').map((item) => item.trim()).filter(Boolean)
  s.testBasis = first('实验信息', '检测依据')
  normalizeSampleBasisState()
  s.standardJudge = first('实验信息', '判定标准', '标准/判定') || s.testBasis
  s.testBasisSingle = first('实验信息', '检测依据范围') === '一单一库内'

  const scheme = savedSchemeIdentity(row, summary)
  s.schemeName = scheme.name
  s.schemeCode = scheme.code
  s.testPlan = scheme.label
  s.centerPrefix = scheme.centerPrefix
  s.seal = first('委托信息', '盖章要求') || s.seal

  s.sampleNo = ''
  s.reportCategory = '普通'
  s.baseReportNo = ''
}

function copyFromEntrust(e: EntrustOrder) {
  const currentEntrustDate = f.entrustDate || businessToday()
  const generatedEntrustNo = f.entrustNo
  if (e.info) Object.assign(f, { ...e.info })
  f.client = e.client || f.client
  f.projectName = e.projectName || f.projectName
  f.entrustDate = currentEntrustDate
  f.entrustNo = generatedEntrustNo
  copyDialogOpen.value = false
  ElMessage.success(`已复制委托 ${e.entrustNo} 的信息到当前表单，可继续修改`)
}
async function copyFromSample(row: SampleRow) {
  if (derivedSchemeLocked.value) return ElMessage.warning('派生报告请通过原报告选择继承信息，检测方案和部门不可替换')
  if (sampleImageBlocked.value) return ElMessage.warning('请等待原商标图样加载完成后再复制')
  const isCurrent = sampleFormSession()
  const currentRead = beginCopySearch()
  const fixedSampleNo = effectiveReportNo.value ? s.sampleNo : ''
  let sourceAccepted = false
  copyLoading.value = true
  copyError.value = ''
  try {
    const d = await fetchSampleCopySource(row.reportNo)
    if (!isCurrent() || !currentRead()) return
    sourceAccepted = true
    copyLoading.value = false
    copyDialogOpen.value = false
    const raw = (d as unknown as { rawSample?: Record<string, unknown> })?.rawSample
    if (raw) {
      // Copy only fields owned by the sample form, never saved workflow metadata.
      const formFields = Object.fromEntries(Object.keys(sampleBlank()).filter(key => key in raw && raw[key] !== undefined).map(key => [key, JSON.parse(JSON.stringify(raw[key]))]))
      Object.assign(s, sampleBlank(), { locationWorkflowVersion: 0 }, formFields)
      normalizeSampleBasisState()
      s.subItems = normalizeSubprojects(raw.subItems)
      const scheme = savedSchemeIdentity(row, d?.summary ?? [])
      s.schemeName = s.schemeName || scheme.name
      s.schemeCode = s.schemeCode || scheme.code
      s.testPlan = s.testPlan || scheme.label
      s.centerPrefix = s.centerPrefix || scheme.centerPrefix
      // “已有表单复制”只复用填写内容，不复用原报告/样品标识。
      // 历史演示数据曾在这三个字段末尾写入“-添加样品”，复制时清理该展示性尾缀。
      s.sampleName = cleanCopiedSampleText(s.sampleName)
      s.spec = cleanCopiedSampleText(s.spec)
      s.manufacturer = cleanCopiedSampleText(s.manufacturer)
      s.sampleNo = ''
      s.reportCategory = '普通'; s.baseReportNo = ''; s.subSuffix = ''  // 复制为新样品
    } else {
      restoreLegacySampleForm(row, d?.summary ?? [])
    }
    if (d.requestedSeal !== undefined) s.seal = d.requestedSeal
    s.engineeringName = savedEngineeringName(d)
    Object.assign(s, savedSampleDates(d))
    s.sampleNo = fixedSampleNo
    if (selectedBasisCodes().length) {
      await hydrateStandardOptions(selectedBasisCodes())
      if (!isCurrent()) return
      await loadCapabilityItems()
    }
    if (!isCurrent()) return
    ElMessage.success(`已复制样品 ${row.sampleNo} 的信息到当前表单，可继续修改`)
  } catch (e) {
    if (!isCurrent()) return
    if (!sourceAccepted && !currentRead()) return
    ElMessage.error(e instanceof Error ? e.message : '复制失败')
    copyError.value = e instanceof Error ? e.message : '复制失败，请重试'
  } finally {
    if (isCurrent() && currentRead()) copyLoading.value = false
  }
}

// 原报告读取完整登记快照，不只使用下拉列表的编号摘要。
let sourceReadVersion = 0
async function selectSourceReport(row: { reportNo: string; mainReportNo?: string; sampleNo: string }) {
  if (readOnly.value || submitting.value || effectiveReportNo.value) return
  const target = row.mainReportNo || row.reportNo
  const category = s.reportCategory
  const suffix = s.subSuffix
  const sessionCurrent = sampleFormSession()
  const version = ++sourceReadVersion
  const current = () => sessionCurrent() && version === sourceReadVersion && s.baseReportNo === target && s.reportCategory === category
  sampleFormLoading.value = true
  sampleFormError.value = ''
  try {
    const d = await fetchSampleCopySource(target)
    if (!current()) return
    if (d.reportNo !== target || !d.entrustSnapshot?.entrustNo) throw new Error('原报告委托信息不完整，请先核对原报告')
    // Legacy summary supplies missing fields; saved form values remain authoritative.
    restoreLegacySampleForm(d, d.summary || [])
    const raw = d.rawSample || {}
    const fields = Object.fromEntries(Object.keys(sampleBlank()).filter(key => key in raw && raw[key] !== undefined)
      .map(key => [key, JSON.parse(JSON.stringify(raw[key]))]))
    Object.assign(s, fields, savedSampleDates(d), {
      sampleNo: d.sampleNo, reportCategory: category, baseReportNo: target, subSuffix: suffix,
      testDept: String(d.department || raw.testDept || s.testDept || ''),
    })
    const scheme = savedSchemeIdentity(d, d.summary || [])
    s.schemeCode = s.schemeCode || scheme.code
    s.schemeName = s.schemeName || scheme.name
    s.testPlan = s.testPlan || scheme.label
    s.centerPrefix = s.centerPrefix || scheme.centerPrefix
    s.testRoom = s.testDept
    if (category === '英文') s.reportLanguage = 'EN'
    if (d.requestedSeal !== undefined) s.seal = d.requestedSeal
    s.subItems = normalizeSubprojects(raw.subItems ?? s.subItems)
    normalizeSampleBasisState()
    sourceSample.value = { reportNo: target, sampleNo: d.sampleNo }
    const snapshot = d.entrustSnapshot
    inheritedEntrustSnapshot.value = JSON.parse(JSON.stringify(snapshot))
    sampleEntrustNo.value = snapshot.entrustNo
    sampleSelectedContract.value = undefined
    Object.assign(sampleEntrust, entrustBlank(), snapshot.info || {}, {
      entrustNo: snapshot.entrustNo, contractNo: snapshot.contractNo, erpContractNo: snapshot.contractNo,
      client: snapshot.client, projectName: snapshot.projectName, projectType: snapshot.projectType,
      handleDept: snapshot.department, handler: snapshot.owner,
    })
    applyCurrentSampleRegistrar()
    await nextTick()
    if (!current()) return
    if (selectedBasisCodes().length) {
      await hydrateStandardOptions(selectedBasisCodes())
      if (!current()) return
      await loadCapabilityItems(true)
    }
    if (current()) ElMessage.success('已带入原报告的委托及样品登记信息，检测方案和部门已锁定')
  } catch (error) {
    if (current()) {
      sampleFormError.value = error instanceof Error ? error.message : '原报告加载失败，请重新选择'
      ElMessage.error(sampleFormError.value)
    }
  } finally {
    if (sessionCurrent() && version === sourceReadVersion) sampleFormLoading.value = false
  }
}

// 样品更改：预填该报告的样品信息（保留委托信息），提交完整更改
const changeEntrustFields = ref<[string, string][]>([])
const sampleFormLoading = ref(false)
const sampleFormError = ref('')
const sampleEditVersion = ref<number>()
const entrustEditVersion = ref<number>()
const sampleImageLoading = ref(false)
const sampleImageError = ref('')
const sampleImageRevision = ref('')
const sampleImageBlocked = computed(() => sampleImageLoading.value || Boolean(sampleImageError.value))
async function loadSavedSampleImage() {
  if (sampleImageLoading.value || !sampleImageRevision.value || !props.changeReportNo) return
  const isCurrent = sampleFormSession()
  const target = props.changeReportNo
  sampleImageLoading.value = true
  sampleImageError.value = ''
  try {
    const image = await fetchSampleFormImage(target, resolvedDetailView.value, sampleImageRevision.value)
    if (!isCurrent()) return
    if (image.reportNo !== target || typeof image.trademarkImage !== 'string') throw new Error('商标图样响应异常，请关闭后重试')
    s.trademarkImage = image.trademarkImage
    // Update only the saved image baseline, never absorb text edits made while
    // the image request was pending.
    if (initialSampleSnapshot.value) {
      const baseline = JSON.parse(initialSampleSnapshot.value)
      baseline.form.trademarkImage = image.trademarkImage
      initialSampleSnapshot.value = JSON.stringify(baseline)
    }
  } catch (error) {
    if (isCurrent()) sampleImageError.value = error instanceof Error ? error.message : '商标图样加载失败，请重试；原图不会被清除'
  } finally {
    if (isCurrent()) sampleImageLoading.value = false
  }
}
async function preloadChange() {
  if (!props.changeReportNo) return
  const target = props.changeReportNo
  const isCurrent = sampleFormSession()
  const d = await fetchReportDetail(target, resolvedDetailView.value, 'sample_form_text')
  if (!isCurrent()) return
  if (!d) throw new Error('样品资料加载失败，请关闭后重试')
  sampleEditVersion.value = d.editVersion
  sampleConfirmedContractNo.value = d.erpContractNo || ''
  legacyMigrationHold.value = Boolean((d.rawSample as Record<string, unknown> | undefined)?.legacyRegistrationReviewRequired)
  // Columns returned by the API are authoritative; older rawSample snapshots
  // may still contain the pre-allocation blank or **** placeholder.
  const identity = d as { reportNo?: string; sampleNo?: string } | null
  const savedReportNo = identity?.reportNo || target
  const savedSampleNo = identity?.sampleNo || savedReportNo.slice(savedReportNo.indexOf('-') + 1)
  activeSampleRegState.value = (d as unknown as { sampleRegState?: string })?.sampleRegState || '登记完成'
  const sum = d?.summary ?? []
  changeEntrustFields.value = (sum.find((x) => x.title === '委托信息')?.fields ?? []) as [string, string][]
  const raw = d?.rawSample
  if (raw) {
    Object.assign(s, sampleBlank(), { locationWorkflowVersion: 0 }, raw)
    Object.assign(s, savedSampleDates(d))
    s.sampleNo = savedSampleNo
    s.centerPrefix = savedReportNo.split('-')[0] || s.centerPrefix
    normalizeSampleBasisState()
    s.subItems = normalizeSubprojects(raw.subItems)
  } else {
    const find = (sec: string, k: string) => (sum.find((x) => x.title === sec)?.fields.find(([kk]) => kk === k)?.[1] as string) || ''
    s.locationWorkflowVersion = 0
    Object.assign(s, savedSampleDates(d))
    s.sampleNo = savedSampleNo
    s.centerPrefix = savedReportNo.split('-')[0] || ''
    const standardValue = (key: string) => {
      const value = find('实验信息', key).trim()
      return value === '—' ? '' : value
    }
    s.sampleName = find('送样信息', '样品名称') || find('样品信息', '样品名称')
    s.spec = find('送样信息', '规格型号'); s.manufacturer = find('送样信息', '生产厂家')
    s.projectList = (find('实验信息', '检测项目') || '').split('、').filter(Boolean)
    s.testBasis = standardValue('检测依据')
    normalizeSampleBasisState()
    s.standardJudge = standardValue('判定标准') || standardValue('标准/判定') || s.testBasis
  }
  s.testDept = s.testDept || d.department || ''
  s.testRoom = s.testDept
  const savedScheme = savedSchemeIdentity({ reportNo: savedReportNo, sampleNo: savedSampleNo }, sum)
  s.schemeCode = s.schemeCode || savedScheme.code
  s.schemeName = s.schemeName || savedScheme.name
  s.testPlan = s.testPlan || savedScheme.label
  s.reportCategory = String(d.reportCategory || raw?.reportCategory || '普通')
  s.baseReportNo = String(d.mainReportNo || d.derivedFrom || raw?.baseReportNo || '')
  if (s.reportCategory === '英文') s.reportLanguage = 'EN'
  if (!isCurrent()) return
  if (d.requestedSeal !== undefined) s.seal = d.requestedSeal
  s.engineeringName = savedEngineeringName(d)
  const ent = changeEntrustFields.value.find(([k]) => k === '委托单')?.[1] || d.entrustSnapshot?.entrustNo || ''
  if (ent) sampleEntrustNo.value = ent
  if (d?.entrustSnapshot) {
    const snapshot = d.entrustSnapshot
    inheritedEntrustSnapshot.value = JSON.parse(JSON.stringify(snapshot))
    Object.assign(sampleEntrust, entrustBlank(), snapshot.info || {})
    sampleEntrust.entrustNo = snapshot.entrustNo
    sampleEntrust.contractNo = snapshot.contractNo
    sampleEntrust.erpContractNo = snapshot.contractNo
    sampleEntrust.client = snapshot.client
    sampleEntrust.projectName = snapshot.projectName
    sampleEntrust.projectType = snapshot.projectType
    sampleEntrust.handleDept = snapshot.department
    sampleEntrust.handler = snapshot.owner
  } else {
    applySampleEntrustOption(entrustOptions.value.find((option) => option.entrustNo === sampleEntrustNo.value))
  }
  applyCurrentSampleRegistrar()
  const image = d as typeof d & { trademarkImageDeferred?: boolean; trademarkImageRevision?: string }
  if (image.trademarkImageDeferred) {
    if (!image.trademarkImageRevision) throw new Error('商标图样加载标识缺失，请关闭后重试')
    sampleImageRevision.value = image.trademarkImageRevision
    void loadSavedSampleImage()
  }
}
async function saveSampleChange(action: 'save' | 'complete' = 'complete') {
  if (submitting.value || readOnly.value) return
  if (judgmentInput.value?.hasPending) return ElMessage.warning('请先添加或取消尚未保存的判定标准')
  if (sampleImageBlocked.value) return ElMessage.warning('原商标图样尚未加载完成，不能保存，请等待或重试图样')
  if (sampleFormLoading.value || sampleFormError.value) return ElMessage.warning('样品资料尚未加载完成，不能保存')
  const isCurrent = sampleFormSession()
  const target = props.changeReportNo!
  const editingDraft = activeSampleRegState.value === '登记中' || (!props.inPlace && action === 'save')
  if (!editingDraft && !s.projectList.length) return ElMessage.warning('请选择检测项目（可多选）')
  const dateErrors = [...sampleDateErrors(!editingDraft), ...samplePricingErrors(s.subItems, s.stdPrice, !editingDraft, sampleContractType.value)]
  if (dateErrors.length) return ElMessage.warning(dateErrors.join('、'))
  submitting.value = true
  invalidateEntrustDocument()
  try {
    if (!(await confirmEntrustProjectName(true)) || !isCurrent()) return
    const item = currentSampleItem()
    if (props.inPlace || administratorEditing.value) {
      // 就地修改：直接保存登记信息，不改状态、不重走评审
      const updated = await editReportInPlace(target, { fullDetail: buildDetail(item), editVersion: sampleEditVersion.value }, administratorEditing.value)
      if (!isCurrent()) return
      sampleEditVersion.value = updated.editVersion
      const savedReportNo = updated.reportNo || target
      invalidateEntrustDocument()
      ElMessage.success(`${savedReportNo} 已保存修改`)
      initialSampleSnapshot.value = sampleSnapshot()
      if (administratorEditing.value) administratorBaseline = administratorSnapshot()
      emit('updated', savedReportNo)
      return
    }
    if (action === 'save') {
      const saved = await saveEntrustChange(target, { fullDetail: buildDetail(item), editVersion: sampleEditVersion.value })
      if (!isCurrent()) return
      invalidateEntrustDocument()
      initialSampleSnapshot.value = sampleSnapshot()
      sampleEditVersion.value = saved.editVersion
      ElMessage.success('已保存修改，仍处于委托更改中，尚未提交')
      emit('updated', saved.reportNo || target)
      return
    }
    const res = await changeResubmit(target, { fullDetail: buildDetail(item), editVersion: sampleEditVersion.value })
    if (!isCurrent()) return
    const dest = res?.status === '检测更改中' ? '进入检测更改' : '重新进入合同评审'
    invalidateEntrustDocument()
    ElMessage.success(`${target} 样品更改完成，${dest}`)
    initialSampleSnapshot.value = sampleSnapshot()
    emit('created', target)
  } catch (e) {
    if (!isCurrent()) return
    ElMessage.error(e instanceof Error ? e.message : '提交失败')
  } finally {
    if (isCurrent()) submitting.value = false
  }
}

async function validateCurrentSample() {
  const errors: string[] = []
  if (s.capabilityEntryIds.length) {
    await loadCapabilityItems()
    if (capabilityError.value) errors.push(capabilityError.value)
    if (unavailableCapabilityIds.value.length) errors.push('存在当前不可用的历史参数，请移除或重新选择后完成登记')
  }
  s.testRoom = s.testDept
  if (!s.schemeCode) errors.push('请选择检测方案')
  if (!s.testDept) errors.push('请选择检测部门/检测室')
  if (!s.testBasis) errors.push('请选择检测依据')
  if (s.locationWorkflowVersion === 1) {
    syncParameterLocations()
    if (parameterLocationError.value) errors.push(parameterLocationError.value)
    if (s.isOnsiteTesting && !s.testLocation) errors.push('请填写现场检测完整地址')
  } else {
    if (!s.testLocation && !s.capabilityEntryIds.length) errors.push('请填写检测地点完整地址')
  }
  if (!s.capabilityEntryIds.length && !s.manualCapabilityItems.length) errors.push('请选择能力项目/参数，或填写库外项目')
  errors.push(...sampleDateErrors())
  errors.push(...samplePricingErrors(s.subItems, s.stdPrice, true, sampleContractType.value))
  if (s.reportCategory === '普通') {
    if (!s.centerPrefix) errors.push('请选择报告标题/检测中心')
  } else {
    if (!s.baseReportNo) errors.push('请选择原报告')
    if (s.reportCategory === '分项' && !s.subSuffix.trim()) errors.push('请填写分项报告后缀')
  }
  sampleConfigErrors.value = errors
  if (errors.length) {
    ElMessage.warning(errors.join('、'))
    document.querySelector('[data-ui~=entrust-dialog] [data-ui~=sample-progress-row]')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return false
  }
  configChecking.value = true
  try {
    const result = await validateSampleConfiguration({
      schemeCode: s.schemeCode,
      department: s.testDept,
      project: s.projectList.join('、'),
      testRoom: s.testRoom,
      testBasis: s.testBasis,
      testBases: [...selectedBasisCodes()],
      standardItemIds: [...s.standardItemIds],
      standardJudge: s.standardJudge || s.testBasis,
      seal: s.seal,
    })
    sampleConfigErrors.value = result.errors
    if (!result.ready) {
      ElMessage.error(`方案配置校验未通过：${result.errors.join('；')}`)
      return false
    }
    return true
  } catch (e) {
    sampleConfigErrors.value = [e instanceof Error ? e.message : '方案配置校验失败']
    return false
  } finally {
    configChecking.value = false
  }
}

const emptySampleDatePlaceholder = /^[-‐‑‒–—―﹘﹣－]+$/u

function hasSampleDateValue(value: unknown): boolean {
  const text = String(value ?? '').trim()
  return Boolean(text)
    && !emptySampleDatePlaceholder.test(text)
    && text !== '待填写'
    && text !== '待录入'
}

function sampleDateErrors(requireSend = true): string[] {
  const errors: string[] = []
  if (!session.canOverrideWorkflowDate && !selectedEntrustDate.value) errors.push('所选委托单缺少委托日期')
  if (requireSend && !hasSampleDateValue(s.sendDate)) errors.push('请选择送样日期')
  const values: [string, string][] = [
    [s.productionDates.length ? '' : s.produceDate, '生产日期'],
    [s.sendDate, '送样日期'],
    [s.sendOutTime, '外部报告承诺日期'],
    [s.sendInTime, '内部报告承诺日期'],
    [s.innerStdDate, '约定检测日期'],
  ]
  if (isSamplingBusiness.value) {
    values.push(
      [s.sampleTime, '抽样日期'],
      [s.sampleArrivalDate, '样品到达日期'],
    )
  }
  for (const [value, label] of values) {
    if (hasSampleDateValue(value) && !(label === '生产日期' ? isProductionDateValid(value) : isWorkflowDateValid(value))) errors.push(`${label}格式无效`)
  }
  errors.push(...sampleDateOrderErrors({ ...s, entrustDate: selectedEntrustDate.value }))
  if (!selectedEntrustDate.value || session.canOverrideWorkflowDate) return errors
  const checks: [string, string, string][] = [
    [s.sendOutTime, sampleFlowBaseDate.value, '外部报告承诺日期'],
    [s.sendInTime, sampleFlowBaseDate.value, '内部报告承诺日期'],
    [s.innerStdDate, sampleFlowBaseDate.value, '约定检测日期'],
  ]
  if (isSamplingBusiness.value) {
    checks.push(
      [s.sampleArrivalDate, s.sendDate || selectedEntrustDate.value, '样品到达日期'],
    )
  }
  for (const [value, previous, label] of checks) {
    if (hasSampleDateValue(value) && isWorkflowDateBefore(value, previous)) errors.push(`${label}不能早于前序流程日期`)
  }
  return errors
}

function currentSampleItem(): SampleItem {
  const optionById = new Map(capabilityOptions.value.map((item) => [item.id, item]))
  const previousById = new Map(s.capabilitySnapshots.map((item) => [item.id, item]))
  return {
    ...s,
    commissionText: { basis: commissionBasisText.value, items: commissionItemsText.value },
    testCategory: s.testCategory,
    testItemOrder: selectedTestItemOrder.value.map(item => ({ ...item })),
    capabilitySnapshots: s.capabilityEntryIds
      .map((id) => optionById.get(id) || previousById.get(id))
      .filter((item): item is CapabilityItemRow => Boolean(item)),
    project: s.projectList.join('、'),
    subItems: normalizeSubprojects(s.subItems),
    sampleNo: s.reportCategory !== '普通' ? sampleAutoNo.value : s.sampleNo,
    reportNo: sampleReportNo.value,
    reportPrefix: reportPrefix.value,
    entrustSnapshot: sampleEntrustPayload(),
  }
}

function validateSampleDraft() {
  const errors: string[] = []
  if (s.reportCategory === '普通') {
    if (!s.schemeCode) errors.push('请选择检测方案，以生成稳定的报告编号')
    if (!s.centerPrefix) errors.push('请选择报告标题/检测中心')
  } else {
    if (!s.baseReportNo) errors.push('请选择原报告')
    if (s.reportCategory === '分项' && !s.subSuffix.trim()) errors.push('请填写分项报告后缀')
  }
  errors.push(...sampleDateErrors(false))
  errors.push(...samplePricingErrors(s.subItems, s.stdPrice, false))
  sampleConfigErrors.value = errors
  if (!errors.length) return true
  ElMessage.warning(errors.join('、'))
  return false
}

// 打开时按模式加载下拉数据
watch(() => [props.modelValue, props.changeReportNo, props.mode, props.editEntrust?.id] as const, async ([open]) => {
  ++sampleFormEpoch
  entrustExportOpen.value = false
  if (open) {
    previewTemplateChosen.value = false
    previewLanguage.value = 'CN'
  }
  const isCurrent = sampleFormSession()
  ++sampleContextEpoch
  ++capabilityRequestSeq
  ++stdSearchRequestSeq
  ++basisSearchRequestSeq
  capabilityLoading.value = false
  stdLoading.value = false
  sampleFormLoading.value = false
  sampleFormError.value = ''
  inheritedEntrustSnapshot.value = undefined
  sampleImageLoading.value = false
  sampleImageError.value = ''
  sampleImageRevision.value = ''
  initialSampleSnapshot.value = ''
  correctedReportNo.value = ''
  if (!open) {
    pendingCloseAction = null
    draftDecisionOpen.value = false
    return
  }
  if (props.mode === 'entrust') {
    // Persisted values must be visible before unrelated network requests finish.
    const restoreSessionDraft = props.editEntrust ? false : await shouldRestoreEntrustDraft()
    if (!isCurrent()) return
    claimedContracts.value = []
    organizationDepartments.value = []
    handleDepts.value = []
    const editId = Number(props.editEntrust?.id)
    activeEntrustId.value = Number.isFinite(editId) && editId > 0 ? editId : null
    entrustEditVersion.value = props.editEntrust?.editVersion
    activeEntrustStatus.value = props.editEntrust?.status || '委托中'
    activeEntrustCompletionAccount.value = props.editEntrust?.completionAccount || ''
    if (!props.editEntrust) {
      Object.assign(f, entrustBlank())
      if (restoreSessionDraft) restoreDraft()
      f.entrustDate = businessToday()
      f.handleDept = f.handleDept || session.dataScope.department || ''
      f.handler = f.handler || session.userName
    }
    clearEntrustErrors()
    draftSavedAt.value = ''
    // 修改模式：预填该委托单已登记信息
    if (props.editEntrust) {
      try { await rememberCorrection('entrusts', props.editEntrust.id!) } catch (e) { ElMessage.error(String(e)); return }
      if (!isCurrent()) return
      const persistedInfo = props.editEntrust.info || {}
      const hasPersisted = (key: string) => Object.prototype.hasOwnProperty.call(persistedInfo, key)
      Object.assign(f, entrustBlank())
      Object.assign(f, persistedInfo)
      if (!hasPersisted('contractNo')) f.contractNo = props.editEntrust.contractNo || ''
      if (!hasPersisted('erpContractNo')) f.erpContractNo = props.editEntrust.contractNo || ''
      if (!hasPersisted('erpType')) f.erpType = props.editEntrust.erpProjectType || ''
      if (!hasPersisted('contractPartyA')) f.contractPartyA = props.editEntrust.contractPartyA || props.editEntrust.client || ''
      if (!hasPersisted('otherPartyA')) f.otherPartyA = props.editEntrust.otherPartyA || ''
      if (!hasPersisted('client')) f.client = props.editEntrust.client
      if (!f.entrustDate) f.entrustDate = props.editEntrust.entrustDate || props.editEntrust.date || ''
      if (!f.projectName) f.projectName = props.editEntrust.projectName
      f.handleDept = ensureHandleDepartmentOption(
        f.handleDept || persistedInfo.handleDepartment || props.editEntrust.handlerDepartment || props.editEntrust.department || '',
        props.editEntrust.handlerDepartment || '',
      )
      if (!f.handler) f.handler = props.editEntrust.handler || props.editEntrust.owner || ''
    } else {
      f.entrustDate = businessToday()
      f.handleDept = ensureHandleDepartmentOption(f.handleDept || session.dataScope.department || '')
      if (!f.handler) f.handler = session.userName
    }
    initialEntrustSnapshot.value = JSON.stringify(f)
    // Options refresh independently. Late responses never write persisted fields
    // or replace edits made while the requests were pending.
    const initialContractNo = f.contractNo
    const contractsLoad = initialContractNo ? fetchContractSelectionPage('', 1, undefined, initialContractNo).then(result => {
      if (isCurrent() && f.contractNo === initialContractNo) claimedContracts.value = result.rows
    }).catch(() => undefined) : Promise.resolve()
    const departmentsLoad = Promise.all([
      fetchHandleDepartments().catch(() => ({ rows: [], current: '' })),
      fetchDepartments().catch(() => []),
    ]).then(([hd, departments]) => {
      if (!isCurrent()) return
      organizationDepartments.value = departments
      handleDepts.value = hd.rows.map(department => ({
        ...department,
        fullName: findOrganizationDepartment(department.name)?.fullName || department.name,
      }))
      if (!props.editEntrust && !f.handleDept && hd.current) {
        f.handleDept = hd.current
        const initial = JSON.parse(initialEntrustSnapshot.value)
        initial.handleDept = hd.current
        initialEntrustSnapshot.value = JSON.stringify(initial)
      }
      // Keep a saved/typed department visible even if it is absent from options.
      ensureHandleDepartmentOption(f.handleDept, props.editEntrust?.handlerDepartment || '')
    })
    if (!props.editEntrust) {
      let number = ''
      try { number = await fetchNextEntrustNo() } catch { /* Existing empty-number behavior. */ }
      if (!isCurrent()) return
      f.entrustNo = number
      const initial = JSON.parse(initialEntrustSnapshot.value)
      initial.entrustNo = number
      initialEntrustSnapshot.value = JSON.stringify(initial)
    }
    await Promise.all([contractsLoad, departmentsLoad])
  } else {
    sampleConfirmedContractNo.value = ''
    sampleEditVersion.value = undefined
    activeSavedReportNo.value = ''
    submitting.value = false
    Object.assign(s, sampleBlank())
    changeEntrustFields.value = []
    sampleEntrustNo.value = ''
    Object.assign(sampleEntrust, entrustBlank())
    if (!isChange.value) {
      activeSampleRegState.value = '登记中'
      sampleEditVersion.value = undefined
      activeSavedReportNo.value = ''
      Object.assign(s, sampleBlank())
      samples.splice(0, samples.length)
      sampleEntrustNo.value = ''
      Object.assign(sampleEntrust, entrustBlank())
    }
    sampleFormLoading.value = isChange.value
    // Start the selected record immediately; unrelated option lists must not
    // delay displaying the persisted form. Every result retains session guards.
    const detailLoad = isChange.value ? preloadChange().then(() => '', error => error instanceof Error ? error.message : '样品资料加载失败，请关闭后重试') : Promise.resolve('')
    const [entrusts, departments] = await Promise.all([
      fetchEntrustOptions().catch(() => []),
      fetchDepartments().catch(() => []),
    ])
    if (!isCurrent()) return
    entrustOptions.value = entrusts
    organizationDepartments.value = departments
    // Original sample search is paginated and opened on demand.
    // 从「新增委托」跳转而来时，预选该委托单
    if (!isChange.value && props.presetEntrustNo && entrustOptions.value.some((o) => o.entrustNo === props.presetEntrustNo)) {
      sampleEntrustNo.value = props.presetEntrustNo
      onSampleEntrustChange(props.presetEntrustNo)
    }
    // 样品更改：预填该报告的样品信息
    const detailError = await detailLoad
    if (!isCurrent()) return
    if (detailError) {
      sampleFormError.value = detailError
      sampleFormLoading.value = false
      return
    }
    if (isChange.value) {
      if (!sampleEntrust.entrustNo) applySampleEntrustOption(entrustOptions.value.find(option => option.entrustNo === sampleEntrustNo.value))
      try {
        await hydrateStandardOptions(selectedBasisCodes())
        if (!isCurrent()) return
        await loadCapabilityItems()
      } catch (error) {
        if (!isCurrent()) return
        sampleFormError.value = error instanceof Error ? error.message : '标准参数加载失败，请关闭后重试'
        sampleFormLoading.value = false
        return
      }
    }
    if (!isCurrent()) return
    initialSampleSnapshot.value = sampleSnapshot()
    sampleFormLoading.value = false
  }
}, { immediate: true })

function entrustPayload() {
  return {
    editVersion: entrustEditVersion.value,
    contractNo: f.erpContractNo || f.contractNo,
    client: f.client,
    projectName: f.projectName,
    projectType: f.projectType,
    department: f.handleDept || props.department,
    info: { ...f },
  }
}

async function persistEntrust() {
  const res = activeEntrustId.value
    ? await updateEntrust(activeEntrustId.value, entrustPayload(), administratorEditing.value)
    : await createEntrust(entrustPayload())
  if (!res.id) throw new Error('委托单保存结果缺少记录标识')
  entrustEditVersion.value = res.editVersion
  activeEntrustId.value = res.id
  activeEntrustStatus.value = res.status || activeEntrustStatus.value
  f.entrustNo = res.entrustNo || f.entrustNo
  initialEntrustSnapshot.value = JSON.stringify(f)
  if (administratorEditing.value) administratorBaseline = administratorSnapshot()
  clearEntrustDraft()
  return res
}

async function confirmEntrustProjectName(sample = false) {
  const isCurrent = sampleFormSession()
  const form = sample ? sampleEntrust : f
  const snapshot = JSON.stringify(form)
  const contractNo = form.contractNo
  const projectName = form.projectName.trim()
  if (!contractNo || !projectName) return true
  // Reopened drafts and copied entrusts may not have loaded their contract yet.
  const selected = sample ? sampleSelectedContract.value : selectedContract.value
  const contract = (selected?.agreementNo === contractNo ? selected : undefined) || (await fetchContractSelectionPage('', 1, undefined, contractNo))
    .rows.find(row => row.agreementNo === contractNo)
  if (!isCurrent() || JSON.stringify(form) !== snapshot) return false
  if (contract?.info?.fromErp !== '1' || projectName !== contract.projectName.trim()) return true
  try {
    await ElMessageBox.confirm(
      `项目名称尚未修改，仍为外部ERP合同自动带入的“${contract.projectName}”。该名称后续会用于报告二维码核验页的工程名称，请核对是否适用。是否继续保存？`,
      '请确认项目名称',
      { type: 'warning', confirmButtonText: '继续保存', cancelButtonText: '返回修改', closeOnClickModal: false },
    )
    return isCurrent() && JSON.stringify(form) === snapshot
  } catch {
    if (isCurrent()) {
      await nextTick()
      const field = document.querySelector<HTMLElement>('[data-ui~=entrust-dialog] [data-field="projectName"]')
      field?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
      field?.querySelector('input')?.focus()
    }
    return false
  }
}

async function saveEntrust() {
  if (submitting.value) return
  submitting.value = true
  try {
    if (!(await confirmEntrustProjectName())) return
    const res = await persistEntrust()
    ElMessage.success(`委托单 ${res.entrustNo} 已保存，当前状态为「${entrustStatusLabel.value}」`)
    emit('entrust-updated', res.entrustNo)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function completeEntrustRegistration() {
  if (submitting.value) return
  if (!validateEntrust()) return ElMessage.warning(`请完成必填项：${entrustErrorList.value.join('、')}`)
  submitting.value = true
  try {
    if (!(await confirmEntrustProjectName())) return
    const saved = await persistEntrust()
    if (!saved.id) throw new Error('委托单保存结果缺少记录标识')
    const completed = saved.status === '委托完成'
      ? saved
      : await completeEntrust(saved.id)
    activeEntrustStatus.value = completed.status
    activeEntrustCompletionAccount.value = session.account
    ElMessage.success(`委托单 ${completed.entrustNo} 已完成登记`)
    if (props.editEntrust) emit('entrust-updated', completed.entrustNo)
    else emit('entrust-created', completed.entrustNo)
    clearEntrustDraft()
    draftSavedAt.value = ''
    initialEntrustSnapshot.value = JSON.stringify(f)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '完成登记失败')
  } finally {
    submitting.value = false
  }
}

async function undoEntrustCompletion() {
  if (!activeEntrustId.value) return ElMessage.warning('请先保存委托登记')
  submitting.value = true
  try {
    const res = await uncompleteEntrust(activeEntrustId.value)
    activeEntrustStatus.value = res.status
    activeEntrustCompletionAccount.value = ''
    ElMessage.success(`委托单 ${res.entrustNo} 已撤销完成，恢复为「登记中」`)
    emit('entrust-updated', res.entrustNo)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '撤销完成失败')
  } finally {
    submitting.value = false
  }
}

function buildDetail(item: SampleItem) {
  const dash = (v: string) => v || '—'
  const snapshot = item.entrustSnapshot
  const entrustInfo = snapshot.info || {}
  const capabilityText = item.capabilitySnapshots.length
    ? item.capabilitySnapshots.map((entry) => `[${entry.standardCode}] ${entry.objectName}/${entry.itemName}（${entry.site}）`).join('；')
    : '—'
  const manualCapabilityText = item.manualCapabilityItems.length
    ? `${item.manualCapabilityItems.join('、')}${item.manualCapabilityReason ? `（说明：${item.manualCapabilityReason}）` : ''}`
    : '—'
  const basisDocumentText = item.commissionText.basis
  const judgmentDocumentText = item.standardJudge
  const deliveryCopies = digitsOnly(item.deliverStd)
  return {
    projectName: snapshot.projectName,
    trademark: item.trademark,
    trademarkImage: item.trademarkImage,
    summary: [
      { title: '委托信息', fields: [['委托单', snapshot.entrustNo], ['委托日期', entrustInfo.entrustDate || ''], ['合同甲方', entrustInfo.contractPartyA || ''], ['其他甲方（付款方）', entrustInfo.otherPartyA || ''], ['委托单位', snapshot.client], ['委托人', entrustInfo.consignor || ''], ['委托人电话', entrustInfo.consignorPhone || ''], ['工程名称', snapshot.projectName], ['工程地址', entrustInfo.projectAddr || ''], ['外部ERP合同编号', snapshot.contractNo], ['项目类型', snapshot.projectType], ['样品登记部门', snapshot.department], ['样品登记人', snapshot.owner], ['经办人电话', entrustInfo.handlerPhone || ''], ['盖章要求', item.seal]] as [string, string][] },
      { title: '送样信息', fields: [['样品编号', item.sampleNo], ['样品名称', dash(item.sampleName)], ['样品/工程名称', dash(item.sampleName)], ['工程名称（幕墙）', dash(item.engineeringName)], ['规格型号', dash(item.spec)], ['生产厂家', dash(item.manufacturer)], ['检测部门', dash(item.testDept)], ['检测室', dash(item.testRoom)], ['是否加急', item.urgent], ['检测期限', dash(item.deadline)], ['外观', dash(item.appearance)], ['铭牌', dash(item.nameplate)], ['商标', dash(item.trademark)], ['检测地点', dash(item.testLocation)], ['样品数量', dash(item.sampleAmount)], ['数量单位', dash(item.unit)], ['出厂编号', dash(item.factoryNo)], ['生产日期', dash(item.produceDate)], ['送样日期', dash(item.sendDate)], ['报告类型', item.reportType], ['检测类别', dash(item.testCategory)], ['流转状态', '待入库']] as [string, string][] },
      { title: '项目信息', fields: [['委托单备注', dash(item.remark)], ['报告首页备注', dash(item.homepageRemark)]] as [string, string][] },
      { title: '抽样信息', fields: [['抽样单位', dash(item.sampleUnit)], ['抽样人', dash(item.sampler)], ['抽样时间', dash(item.sampleTime)], ['抽样数量', dash(item.sampleQty)], ['基数', dash(item.entrustQty)], ['受检单位', dash(item.inspectedUnit)], ['任务来源', dash(item.taskSource)], ['抽样地点', dash(item.samplingLocation)], ['样品/抽样单编号', dash(item.sampleNo)], ['样品到达日期', dash(item.sampleArrivalDate)], ['样品等级', dash(item.sampleGrade)], ['封样状态', dash(item.sealStatus)], ['检查封样人员', dash(item.sealChecker)]] as [string, string][] },
      { title: '结算信息', fields: [['标准价格', dash(item.stdPrice)], ['缴费情况', dash(item.payStatus)], ['支付方式', dash(item.payWay)], ['已缴费', dash(item.paid)], ['其他', dash(item.otherSettle)]] as [string, string][] },
      { title: '子项目信息', fields: subprojectSummary(item.subItems) },
      { title: '检测子项目信息', fields: technicalSummary(item.detectionSubprojects) },
      { title: '报告发送', fields: [['报告承诺时间(外部)', dash(item.sendOutTime)], ['报告承诺时间(内部)', dash(item.sendInTime)], ['样品处理方式', dash(item.sampleHandle)], ['报告交付方式', dash(item.deliverWay)], ['邮寄地址', dash(item.mailAddr)], ['报告交付份数', dash(deliveryCopies)], ['报告形式', dash(item.reportForm)], ['现场检测时间约定', dash(item.fieldAgreement)], ['约定检测日期', dash(item.innerStdDate)]] as [string, string][] },
      { title: '实验信息', fields: [['检测项目', item.commissionText.items], ['能力项目/参数', capabilityText], ['库外项目', manualCapabilityText], ['检测方案', item.schemeName ? `${item.schemeName}（${item.schemeCode}）` : dash(item.testPlan)], ['检测依据', dash(basisDocumentText)], ['检测依据范围', item.seal.includes('CMA') ? (item.testBasisSingle ? '一单一库内' : '超出一单一库（需复核）') : '—（非CMA盖章）'], ['判定标准', dash(judgmentDocumentText)], ['标准/判定', dash(judgmentDocumentText)], ['执行标准', dash(basisDocumentText)], ['检测设备', '待检测人员录入'], ['检测日期', '待检测人员录入']] as [string, string][] },
      { title: '原始记录', fields: [['记录编号', '待录入'], ['实测值', '待录入'], ['校核状态', '待检测人员录入并上传']] as [string, string][] },
    ],
    checks: [],
    attachments: [],
    entrustSnapshot: snapshot,
    sampleRegistrar: session.userName || session.account || '',
    sampleRegistrarAccount: session.account || '',
    sampleRegistrarDepartment: session.dataScope.department || '',
    // 原始样品表单（供「已有表单复制」一键还原到新表单）
    requestedSeal: item.seal,
    rawSample: { ...item, deliverStd: deliveryCopies, testBasis: item.testBases.join('；') || item.testBasis, testBases: [...item.testBases], subItems: item.subItems.map((x) => ({ ...x })) },
  }
}
const selectedEntrust = computed(() => entrustOptions.value.find((o) => o.entrustNo === sampleEntrustNo.value))
const selectedEntrustDate = computed(() => sampleEntrust.entrustDate || selectedEntrust.value?.workflowDates?.entrustAt || selectedEntrust.value?.entrustDate || '')
const sampleFlowBaseDate = computed(() => s.sendDate || selectedEntrustDate.value)
// 与原业务系统保持一致：新增/修改样品时固定展示抽样信息。
// 非抽样业务允许留空，抽样业务的数据仍写入同一组样品字段。
const isSamplingBusiness = computed(() => true)
const schemeMappingText = computed(() => {
  if (!s.schemeCode) return ''
  const fields = [
    s.centerPrefix,
    s.testCategory,
    s.reportType,
    s.testDept,
    s.projectList.length,
    s.sampleAmount,
    s.appearance,
    s.testLocation,
  ]
  const filled = fields.filter(Boolean).length
  return filled === fields.length
    ? '已带入 8 项：报告标题、检测类别、报告格式、检测部门、检测参数、样品数量、样品状态、检测地点'
    : `方案参数已带入 ${filled} 项，仍有 ${fields.length - filled} 项可手动填写`
})
const schemeDisplay = computed(() => {
  const code = String(s.schemeCode || '').trim()
  const name = String(s.schemeName || '').trim()
  return [code, name].filter(Boolean).join(' · ')
})

async function saveSamples(regState: '登记中' | '登记完成' = '登记完成') {
  if (submitting.value) return
  if (judgmentInput.value?.hasPending) return ElMessage.warning('请先添加或取消尚未保存的判定标准')
  if (sampleFormLoading.value || sampleFormError.value) return ElMessage.warning('原报告或样品资料尚未完整加载，请重新选择或重试')
  if (sampleImageBlocked.value) return ElMessage.warning('原商标图样尚未加载完成，不能保存，请等待或重试图样')
  if (isChange.value) return saveSampleChange()
  const isCurrent = sampleFormSession()
  if (!sampleEntrustNo.value) return ElMessage.warning('请先选择委托单')
  if (regState === '登记完成' && !canCompleteSampleRegistration.value) return ElMessage.warning('无完成样品登记权限')
  if (regState === '登记完成') {
    if (!(await validateCurrentSample())) return
  } else if (!validateSampleDraft()) return
  if (!isCurrent()) return
  submitting.value = true
  invalidateEntrustDocument()
  try {
    if (!(await confirmEntrustProjectName(true)) || !isCurrent()) return
    const item = currentSampleItem()
    const snapshot = item.entrustSnapshot
    let reportNo = activeSavedReportNo.value
    if (reportNo) {
      const updated = await editReportInPlace(reportNo, { fullDetail: buildDetail(item), editVersion: sampleEditVersion.value }, administratorEditing.value)
      if (!isCurrent()) return
      sampleEditVersion.value = updated.editVersion
      reportNo = updated.reportNo || reportNo
      activeSavedReportNo.value = reportNo
      if (regState === '登记完成' && activeSampleRegState.value !== '登记完成') {
        await sampleRegAction(reportNo, 'complete')
        if (!isCurrent()) return
      }
    } else {
      const res = await createReport({
        // 普通报告：只给前缀，序号后端自动分配；派生报告给完整原号+后缀
        reportNoPrefix: item.reportCategory === '普通' ? item.reportPrefix : undefined,
        reportNo: item.reportCategory === '普通' ? undefined : item.reportNo,
        project: item.project,
        projectName: snapshot.projectName,
        client: snapshot.client,
        template: 'REPORT_THERMAL',
        deadline: '正常',
        department: item.testDept || props.department,
        owner: '',
        entrustNo: sampleEntrustNo.value,
        detail: buildDetail(item),
        baseReportNo: item.reportCategory === '普通' ? undefined : item.baseReportNo || undefined,
        reportCategory: item.reportCategory,
        regState,
      })
      if (!isCurrent()) return
      reportNo = res.reportNo
      sampleEditVersion.value = res.editVersion
      activeSavedReportNo.value = reportNo
      s.sampleNo = res.sampleNo || (
        s.centerPrefix && reportNo.startsWith(`${s.centerPrefix}-`)
          ? reportNo.slice(s.centerPrefix.length + 1)
          : s.sampleNo
      )
    }
    activeSampleRegState.value = regState
    invalidateEntrustDocument()
    ElMessage.success(regState === '登记完成'
      ? `样品单 ${reportNo} 已完成登记，进入合同评审；当前表单保持打开`
      : `样品单 ${reportNo} 已保存，状态为登记中；当前表单保持打开`)
    initialSampleSnapshot.value = sampleSnapshot()
    if (administratorEditing.value) administratorBaseline = administratorSnapshot()
    emit('created', reportNo)
  } catch (e) {
    if (!isCurrent()) return
    ElMessage.error(e instanceof Error ? e.message : '生成失败')
  } finally {
    if (isCurrent()) submitting.value = false
  }
}
useLiveSearch(() => basisKeyword.value, runBasisSearchFromStart, () => basisDialogOpen.value)
useLiveSearch(schemeKeyword, loadSchemes, () => schemeDialogOpen.value)
</script>


