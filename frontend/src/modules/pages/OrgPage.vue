<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">
    <template #header-actions>
    <SecurityAdminPanel />
    <el-button type="primary" plain @click="openPermissionTemplateCenter">权限模板与 Excel</el-button>
    <el-button @click="openAddDept">添加部门</el-button>
    <el-button :disabled="!currentDept" @click="openEditDept">修改部门</el-button>
    <el-button :disabled="!currentDept" type="danger" plain @click="removeDept">删除部门</el-button>
    </template>

  <el-alert
    v-if="!available"
    type="info"
    :closable="false"
    show-icon
    title="本地演示模式：可查看组织机构与部门授权版式，调整不会写入任何平台。"
  />

  <div class="row g-3">
    <div class="col-12 col-xl-3">
    <el-card shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>组织机构</strong>
          <el-tag size="small">{{ deptCount }} 个部门</el-tag>
        </div>
      </template>
      <div class="d-xl-none">
        <el-select :model-value="currentDept?.id" filterable placeholder="选择部门" aria-label="选择部门" @change="selectDept">
          <el-option v-for="department in flatDepts" :key="department.id" :value="department.id" :label="department.indentLabel" />
        </el-select>
      </div>
      <div class="d-none d-xl-block">
      <DataTable label="组织机构" :rows="departmentRows" :columns="departmentColumns" :row-key="row => String(row.id)" :row-label="row => row.name" @row-click="onNodeClick">
        <template #cell-name="{ row }"><button type="button" class="btn btn-link text-start text-wrap text-break w-100 px-2 py-1" :class="currentDept?.id === row.id ? 'bg-primary-subtle fw-semibold' : ''" :aria-current="currentDept?.id === row.id ? 'true' : undefined" :title="row.name" @click.stop="onNodeClick(row)">{{ row.indentLabel }}</button></template>
      </DataTable>
      </div>
    </el-card>
    </div>

    <div class="col-12 col-xl-9">
      <el-empty v-if="!currentDept" description="选择左侧部门后设置部门授权并管理人员" />

      <el-card v-else shadow="never" >
        <template #header>
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
            <div>
              <strong class="d-block text-break">{{ currentDept.name }} · 部门授权</strong>
              <span class="d-block text-muted small mt-1">部门授权是本部门所有人员的权限上限</span>
            </div>
            <el-button
              type="primary"
              :loading="deptAuthSaving"
              :disabled="deptAuth.orgWide"
              @click="saveDepartmentAuth"
            >
              {{ deptAuth.orgWide ? '根机构固定为全部权限' : '保存部门授权' }}
            </el-button>
          </div>
        </template>

        <el-tabs v-model="deptAuthTab">
          <el-tab-pane label="功能授权" name="function">
            <PermissionMenuChecklist v-model="deptPermissionCodes" :permissions="deptAuth.permissions" :disabled="deptAuth.orgWide" />
          </el-tab-pane>

          <el-tab-pane label="项目授权" name="project">
            <p class="text-muted mb-3">部门只设置是否拥有该项目；人员授权时再细分项目下的业务环节</p>
            <el-input v-model="deptProjectKeyword" clearable placeholder="搜索项目名称 / 编号" aria-label="搜索部门授权项目" class="mb-3" />
            <ProjectAuthorizationFilters v-model="deptProjectFilter" :projects="deptAuth.projects" />
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 my-3">
              <span class="text-muted small">筛选结果 {{ filteredDeptProjects.length }} / {{ deptAuth.projects.length }} 项；已选 {{ deptProjectIds.length }} 项，筛选外勾选保持不变</span>
              <div class="d-flex flex-wrap gap-2">
                <el-button link type="primary" :disabled="deptAuth.orgWide || !filteredDeptProjects.length" @click="selectFilteredDeptProjects(true)">全选筛选结果</el-button>
                <el-button link :disabled="deptAuth.orgWide" @click="selectFilteredDeptProjects(false)">清空筛选结果</el-button>
              </div>
            </div>
            <div class="row g-3">
              <div v-for="project in filteredDeptProjects" :key="project.id" class="col-12 col-xxl-6">
              <el-checkbox
                v-model="deptProjectIds"
                :value="project.id"
                :disabled="deptAuth.orgWide"
                class="h-100 w-100 m-0 p-3 ps-5 border rounded text-wrap"
              >
                <span class="d-block fw-medium text-break">{{ project.name }}</span>
                <small class="d-block text-muted text-break mt-1">{{ project.code }} · {{ project.department }}</small>
              </el-checkbox>
              </div>
            </div>
            <el-empty v-if="!filteredDeptProjects.length" description="没有符合筛选条件的项目" />
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <el-card v-if="currentDept" shadow="never" >
        <template #header>
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
            <div>
              <strong>部门人员</strong>
              <el-tag size="small" type="success" >{{ members.length }} 名</el-tag>
            </div>
            <el-button type="primary" @click="openCreateMember">新建人员</el-button>
          </div>
        </template>
        <el-table :data="members" border height="360">
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column prop="account" label="账号" min-width="110" />
          <el-table-column prop="roleName" label="角色" min-width="120" />
          <el-table-column label="账号状态" width="92" align="center">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">{{ row.enabled ? '已启用' : '已停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="所在部门" min-width="220">
            <template #default="{ row }">
              <el-select
                :model-value="row.departmentId"
                filterable
                size="small"
                :loading="movingUserId === row.id"
                @change="(departmentId: number) => moveMember(row, departmentId)"
              >
                <el-option v-for="d in flatDepts" :key="d.id" :label="d.indentLabel" :value="d.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="功能数" width="90" align="center" prop="permissionCount" />
          <el-table-column label="操作" width="390" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openAdjustMember(row)">人员调整</el-button>
              <el-button link type="primary" size="small" @click="openMemberAuth(row)">人员授权</el-button>
              <el-button link size="small" @click="openDataGrant(row)">数据授权</el-button>
              <el-button link size="small" @click="openMemberAuth(row, 'equipment')">仪器授权</el-button>
              <el-button
                link
                type="warning"
                size="small"
                :loading="resettingUserId === row.id"
                @click="resetMemberPassword(row)"
              >
                重置密码
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>

  <el-dialog v-model="memberAuthOpen" :title="`人员授权 · ${memberAuth.user?.name ?? ''}`" width="1080px">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="功能权限仍受所属部门上限约束；项目编号可从全院目录选择，保存时会同步补齐部门项目上限和必要的数据范围。"
    />
    <div >
      <span>功能权限模板（可多选，不影响项目授权）</span>
      <el-select
        v-model="memberTemplateIds"
        multiple
        filterable
        collapse-tags
        collapse-tags-tooltip
        placeholder="选择一个或多个已启用模板"
        
      >
        <el-option
          v-for="item in enabledPermissionTemplates"
          :key="item.id"
          :label="`${item.name}（${item.code}）`"
          :value="item.id"
        />
      </el-select>
      <el-button type="primary" plain :disabled="!memberTemplateIds.length" @click="applySelectedTemplates">
        仅填充功能权限
      </el-button>
    </div>
    <ErpPermissionEditor v-if="memberAuth.erpAuthorization"
      v-model="memberErpRoles"
      :administrator="memberAuth.erpAuthorization.administrator"
      :can-manage="memberAuth.erpAuthorization.canManage"
      :disabled="memberAuthSaving" />
    <div class="mb-3">
      <el-checkbox v-model="memberSealConfirmation" :disabled="memberAuthSaving">报告签章确认</el-checkbox>
      <p class="text-muted small mb-0">人员签字完成后，可在报告签发页确认盖章。需同时具备报告签发页面及相应数据范围权限；管理员也需显式勾选。</p>
    </div>
    <div class="mb-3">
      <el-checkbox v-model="memberCorrectionApproval" :disabled="memberAuthSaving || memberAuth.correctionApprovalInherited">报告更改审批</el-checkbox>
      <p class="text-muted small mb-0">可审批内部／外部更正申请。需同时具备报告更改申请页面及对应数据范围权限；管理员默认拥有审批权限。</p>
    </div>
    <div class="mb-3" role="group" aria-label="报告下载与发放权限">
      <el-checkbox v-model="memberSealedReportDownload" :disabled="memberAuthSaving || memberAuth.reportDeliveryInherited">盖章报告下载（未发放状态）</el-checkbox>
      <p>可在报告签发、报告查询和报告发放中下载签字盖章版，仍遵守原数据范围。报告发放后，所属检测部门人员可在查询和发放中下载。</p>
      <el-checkbox v-model="memberReportDistribution" :disabled="memberAuthSaving || memberAuth.reportDeliveryInherited">报告发放</el-checkbox>
      <p>可办理已归档报告的发放，仍需报告发放页面及原流程范围权限。</p>
      <p v-if="memberAuth.reportDeliveryInherited">此账号继承全平台管理权限，两项操作不受个人勾选限制。</p>
    </div>
    <el-tabs v-model="memberAuthTab">
      <el-tab-pane label="仪器授权" name="equipment">
        <p>默认可使用本人所属部门的仪器。勾选其他部门后，可在检测录入／更改中选择这些部门的仪器，不包含其子部门。</p>
        <p>此授权不增加报告数据范围或仪器维护权限；仪器状态、检定／校准有效期仍按本次试验日期校验。</p>
        <p v-if="memberAuth.equipmentAuthorizationInherited">此账号继承全平台管理权限，可选择所有部门仪器。</p>
        <label for="member-equipment-departments">允许使用仪器的其他部门（可多选）</label>
        <el-select id="member-equipment-departments" v-model="memberEquipmentDepartmentIds" multiple filterable
          :disabled="memberAuthSaving || memberAuth.equipmentAuthorizationInherited" placeholder="请选择授权部门" class="w-100">
          <el-option v-for="item in flatDepts.filter(item => item.id !== memberAuth.department.id)"
            :key="item.id" :value="item.id" :label="item.indentLabel" />
        </el-select>
        <p class="text-muted mt-2">取消部门后，不再允许新增选择该部门的仪器；报告中已保存的仪器记录保留。点击“保存人员授权”后生效。</p>
      </el-tab-pane>
      <el-tab-pane label="功能授权" name="function">
        <PermissionMenuChecklist v-model="memberPermissionCodes" :permissions="memberAuth.permissions" />
      </el-tab-pane>
      <el-tab-pane label="项目授权（业务环节）" name="project">
        <div class="row g-3">
          <aside class="col-12 col-lg-3">
            <header>
              <strong>该人员具备的业务权限</strong>
              <small>基础操作按部门生效，专业岗位按编号授权</small>
            </header>
            <el-empty v-if="!memberRoleSteps.length" description="请先在功能授权中增加业务权限" :image-size="72" />
            <template v-else>
              <button
                v-for="role in memberRoleSteps"
                :key="role.code"
                type="button"
                class="list-group-item list-group-item-action"
                :class="{ active: memberActiveRoleCode === role.code }"
                @click="memberActiveRoleCode = role.code"
              >
                <span>
                  <strong>{{ memberRoleLabel(role) }}</strong>
                  <small>{{ role.name }}</small>
                </span>
                <el-tag v-if="memberIsBasicRole(role.code)" size="small" effect="plain">{{ memberBasicEnabled(role.code) ? '本部门全部项目' : '已撤销' }}</el-tag>
                <el-tag v-else size="small" effect="plain">{{ memberRoleSelectedCount(role.code) }} 项目</el-tag>
              </button>
            </template>
          </aside>
          <section v-if="memberActiveRole && memberIsBasicRole(memberActiveRole.code)" class="col-12 col-lg-9">
            <el-alert title="基础操作默认覆盖本部门全部项目，无需逐个编号授权" type="info" :closable="false" show-icon />
            <p>所属部门：{{ memberAuth.department.name }}。仅在已有数据可见范围内操作，不增加跨部门数据范围。</p>
            <el-checkbox
              :model-value="memberBasicEnabled(memberActiveRole.code)"
              :disabled="!memberBasicAllowed(memberActiveRole.code)"
              @change="(checked: boolean) => toggleMemberBasicRole(memberActiveRoleCode, checked)"
            >允许{{ memberRoleLabel(memberActiveRole) }}</el-checkbox>
            <p>取消勾选可撤销此项基础功能，重新勾选可恢复；点击“保存人员授权”后生效。合同评审、主检、审核、批准仍按各自编号授权。</p>
          </section>
          <section v-else class="col-12 col-lg-9">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
              <div>
                <strong>项目编号汇总表</strong>
                <small>筛选结果 {{ filteredMemberProjects.length }} / 全院 {{ memberAuth.projects.length }} 项，筛选外勾选保持不变</small>
              </div>
              <el-input v-model="memberProjectKeyword" clearable placeholder="搜索项目编号 / 名称 / 部门" class="mb-3" />
            </div>
            <ProjectAuthorizationFilters v-model="memberProjectFilter" :projects="memberAuth.projects" />
            <div v-if="memberActiveRole" class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
              <span>正在配置：{{ memberRoleLabel(memberActiveRole) }}，已选 {{ memberRoleSelectedCount(memberActiveRole.code) }} 项</span>
              <el-button link type="primary" :disabled="!visibleMemberRoleStepIds.length" @click="selectAllVisibleProjectsForRole">全选筛选结果（{{ visibleMemberRoleStepIds.length }}）</el-button>
              <el-button link @click="toggleAllVisibleProjectsForRole(false)">清空筛选结果</el-button>
            </div>
            <el-table v-if="memberActiveRole" :data="filteredMemberProjects" border height="420" >
              <el-table-column width="54" align="center">
                <template #header>
                  <el-checkbox
                    :model-value="allVisibleProjectsSelectedForRole"
                    :indeterminate="someVisibleProjectsSelectedForRole && !allVisibleProjectsSelectedForRole"
                    @change="(checked: boolean) => toggleAllVisibleProjectsForRole(checked)"
                  />
                </template>
                <template #default="{ row }">
                  <el-checkbox
                    :model-value="hasStep(memberProjectStepIds, memberProjectRoleStepId(row, memberActiveRoleCode))"
                    @change="(checked: boolean) => setStep(memberProjectStepIds, memberProjectRoleStepId(row, memberActiveRoleCode), checked)"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="code" label="项目编号" min-width="125" show-overflow-tooltip />
              <el-table-column prop="name" label="项目名称" min-width="190" show-overflow-tooltip />
              <el-table-column prop="department" label="项目归属部门" min-width="155" show-overflow-tooltip />
              <el-table-column prop="location" label="地点" min-width="100" show-overflow-tooltip>
                <template #default="{ row }">{{ row.location || '—' }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="请从左侧选择一项业务权限" :image-size="84" />
          </section>
        </div>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="memberAuthOpen = false">取消</el-button>
      <el-button type="primary" :loading="memberAuthSaving" @click="saveMemberAuth">保存人员授权</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="permissionTemplateOpen" title="人员权限模板与 Excel" width="1040px" destroy-on-close>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="保存模板会同步所有已套用人员的功能权限；多模板取合集，仍受所属部门授权上限约束。项目编号授权和数据范围不受影响。"
    />
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <span>共 {{ permissionTemplateCatalog.rows.length }} 个模板</span>
      <el-button :loading="permissionExporting" @click="exportPermissionExcel">全量导出 Excel</el-button>
      <el-button :loading="permissionImporting" @click="selectPermissionExcel">上传 Excel 全量替换</el-button>
      <el-button type="success" plain :loading="appointmentPreviewLoading" @click="selectAppointmentExcel">任命表预检</el-button>
      <el-button type="primary" @click="openPermissionTemplateEditor()">新建模板</el-button>
      <input
        ref="permissionImportInput"
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        class="d-none"
        @change="handlePermissionExcel"
      />
      <input
        ref="appointmentImportInput"
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        class="d-none"
        @change="handleAppointmentExcel"
      />
    </div>
    <el-table :data="permissionTemplateCatalog.rows" border height="460" v-loading="permissionTemplatesLoading">
      <el-table-column prop="code" label="模板编码" min-width="145" />
      <el-table-column prop="name" label="模板名称" min-width="150" />
      <el-table-column prop="description" label="说明" min-width="210" show-overflow-tooltip />
      <el-table-column label="功能/环节" width="120" align="center">
        <template #default="{ row }">{{ row.permissionCodes.length }} / {{ row.projectStepIds.length }}</template>
      </el-table-column>
      <el-table-column prop="assignedUserCount" label="已套用人员" width="105" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="145" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openPermissionTemplateEditor(row)">编辑</el-button>
          <el-button link type="danger" @click="removePermissionTemplate(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>

  <el-dialog v-model="appointmentPreviewOpen" title="人员权限任命表预检" width="980px" destroy-on-close>
    <el-alert
      :type="appointmentPreview?.blockingErrors.length ? 'error' : 'success'"
      :closable="false"
      show-icon
      :title="appointmentPreview?.blockingErrors.length ? '存在阻断项，不能写入数据库' : '预检通过：确认后仅替换匹配人员的报告相关权限'"
    />
    <el-descriptions v-if="appointmentPreview" :column="4" border >
      <el-descriptions-item label="明细记录">{{ appointmentPreview.sourceRows }}</el-descriptions-item>
      <el-descriptions-item label="人员">{{ appointmentPreview.peopleCount }}</el-descriptions-item>
      <el-descriptions-item label="匹配/异常">{{ appointmentPreview.matchedPeopleCount }} / {{ appointmentPreview.unmatchedPeopleCount }}</el-descriptions-item>
      <el-descriptions-item label="项目编号">{{ appointmentPreview.projectCodeCount }}</el-descriptions-item>
      <el-descriptions-item label="既有编号">{{ appointmentPreview.matchedProjectCodeCount }}</el-descriptions-item>
      <el-descriptions-item label="新增项目">{{ appointmentPreview.newProjectCount }}</el-descriptions-item>
      <el-descriptions-item label="有效任命">{{ appointmentPreview.grantCount }}</el-descriptions-item>
      <el-descriptions-item label="忽略原始记录审核">{{ appointmentPreview.ignoredRowCount }}</el-descriptions-item>
    </el-descriptions>
    <el-tabs v-if="appointmentPreview" >
      <el-tab-pane :label="`异常清单 ${appointmentPreview.exceptions.length}`">
        <el-table :data="appointmentPreview.exceptions" border height="300" empty-text="无异常">
          <el-table-column prop="type" label="类型" width="150" />
          <el-table-column prop="person" label="人员" width="110" />
          <el-table-column prop="projectCode" label="项目编号" width="110" />
          <el-table-column prop="detail" label="说明" min-width="300" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>
      <el-tab-pane :label="`新增项目 ${appointmentPreview.newProjects.length}`">
        <el-table :data="appointmentPreview.newProjects" border height="300">
          <el-table-column prop="projectCode" label="编号" width="100" />
          <el-table-column prop="name" label="报告类别" min-width="180" />
          <el-table-column prop="department" label="归属部门" min-width="150" />
          <el-table-column prop="sourceDepartment" label="授权部门口径" min-width="190" />
          <el-table-column prop="location" label="地点" width="120" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane :label="`未匹配人员 ${appointmentPreview.unmatchedPeople.length}`">
        <el-tag v-for="name in appointmentPreview.unmatchedPeople" :key="name" type="warning" >{{ name }}</el-tag>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="appointmentPreviewOpen = false">取消</el-button>
      <el-button
        type="primary"
        :loading="appointmentApplying"
        :disabled="!appointmentPreview || appointmentPreview.blockingErrors.length > 0"
        @click="applyAppointmentImport"
      >确认仅替换报告相关权限</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="permissionTemplateEditorOpen"
    :title="permissionTemplateForm.id ? '编辑权限模板' : '新建权限模板'"
    width="1080px"
    destroy-on-close
  >
    <el-form label-width="90px" >
      <div class="row g-3">
        <el-form-item class="col-12 col-md-6" label="模板编码"><el-input v-model="permissionTemplateForm.code" maxlength="40" placeholder="如 testing-reviewer" /></el-form-item>
        <el-form-item class="col-12 col-md-6" label="模板名称"><el-input v-model="permissionTemplateForm.name" maxlength="80" /></el-form-item>
        <el-form-item class="col-12 col-md-6" label="是否启用"><el-switch v-model="permissionTemplateForm.enabled" /></el-form-item>
      </div>
      <el-form-item label="说明"><el-input v-model="permissionTemplateForm.description" maxlength="300" show-word-limit /></el-form-item>
    </el-form>
    <el-tabs v-model="permissionTemplateTab">
      <el-tab-pane label="功能权限" name="function">
        <PermissionMenuChecklist v-model="permissionTemplateForm.permissionCodes" :permissions="permissionTemplateCatalog.permissions" />
      </el-tab-pane>
      <el-tab-pane label="项目环节" name="project">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <span>环节必须具备对应功能权限</span>
          <el-input v-model="permissionTemplateProjectKeyword" clearable placeholder="搜索项目名称 / 编号" class="mb-3" />
          <el-button link type="primary" @click="selectAllPermissionTemplateSteps">全选可用环节</el-button>
          <el-button link @click="permissionTemplateForm.projectStepIds = []">清空</el-button>
        </div>
        <div class="row g-3">
          <el-table :data="filteredPermissionTemplateProjects" border height="450" >
            <el-table-column fixed label="项目" min-width="230">
              <template #default="{ row }">
                <strong >{{ row.name }}</strong>
                <small>{{ row.code }} · {{ row.department }}</small>
              </template>
            </el-table-column>
            <el-table-column
              v-for="(step, index) in permissionTemplateCatalog.stepColumns"
              :key="step.code"
              :label="step.name"
              width="120"
              align="center"
            >
              <template #default="{ row }">
                <el-checkbox
                  :model-value="hasStep(permissionTemplateForm.projectStepIds, row.stepIds[index])"
                  :disabled="!canSelectTemplateStep(row.stepIds[index], step)"
                  @change="(checked: boolean) => setStep(permissionTemplateForm.projectStepIds, row.stepIds[index], checked)"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="permissionTemplateEditorOpen = false">取消</el-button>
      <el-button type="primary" :loading="permissionTemplateSaving" @click="savePermissionTemplate">保存模板</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="dataGrantOpen" :title="`数据授权 · ${dataGrantUser?.name ?? ''}`" width="680px">
    <p v-if="dataGrantUser?.dataScope.scopeType === 'department_project'">当前范围：本部门＋授权部门＋授权项目。开启“看数据”后，该部门的样品和报告可见；“含子部门”会一并覆盖下属部门。</p>
    <p v-else-if="dataGrantUser?.dataScope.scopeType === 'self'">当前范围为“仅本人”，部门授权暂不扩大数据范围。需要查看跨部门数据时，请先在用户权限中切换到“指定部门（可跨部门）”。</p>
    <p v-else-if="dataGrantUser?.dataScope.scopeType === 'authorization'">当前范围为“授权范围（待批准）”，部门授权仍受报告状态限制。需要查看全部状态时，请在用户权限中切换到“指定部门（可跨部门）”。</p>
    <p v-else-if="dataGrantUser?.dataScope.scopeType === 'all'">当前可查看全院数据，无需重复加授部门。“看成员”单独控制人员可见范围。</p>
    <p v-else>开启“看数据”可查看所选部门的数据；没有数据授权时默认本部门。“含子部门”会一并覆盖下属部门。</p>
    <p class="text-muted">数据授权只控制可见范围。入库、出库、检测、评审等办理权限仍在“功能授权”和“项目授权（业务环节）”中配置。“看成员”不会授予数据权限。</p>
    <el-table :data="dataGrantUser?.dataGrants ?? []" border size="small" empty-text="暂无跨部门授权">
      <el-table-column prop="departmentName" label="授权部门" min-width="150" />
      <el-table-column label="看数据" width="80" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.seeData" @change="(v: SwitchVal) => saveDataGrant(row.departmentId, { ...row, seeData: Boolean(v) })" />
        </template>
      </el-table-column>
      <el-table-column label="看成员" width="80" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.seeMembers" @change="(v: SwitchVal) => saveDataGrant(row.departmentId, { ...row, seeMembers: Boolean(v) })" />
        </template>
      </el-table-column>
      <el-table-column label="含子部门" width="90" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.includeChildren" @change="(v: SwitchVal) => saveDataGrant(row.departmentId, { ...row, includeChildren: Boolean(v) })" />
        </template>
      </el-table-column>
      <el-table-column label="" width="70">
        <template #default="{ row }"><el-button link type="danger" @click="revokeDataGrant(row.departmentId)">收回</el-button></template>
      </el-table-column>
    </el-table>
    <div >
      <el-select v-model="addGrantForm.departmentId" filterable placeholder="选择加授部门" >
        <el-option v-for="d in flatDepts" :key="d.id" :label="d.indentLabel" :value="d.id" />
      </el-select>
      <el-checkbox v-model="addGrantForm.seeData">看数据</el-checkbox>
      <el-checkbox v-model="addGrantForm.seeMembers">看成员</el-checkbox>
      <el-checkbox v-model="addGrantForm.includeChildren">含子部门</el-checkbox>
      <el-button type="primary" :disabled="!addGrantForm.departmentId" @click="addDataGrant">加授</el-button>
    </div>
  </el-dialog>

  <el-dialog v-model="createMemberOpen" title="新建人员" width="560px" destroy-on-close>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="保存后同时建立人员档案和登录账号，并生成随机初始密码；首次登录必须修改。"
    />
    <el-form label-width="100px" >
      <el-form-item label="人员编号"><el-input v-model="createMemberForm.account" maxlength="40" placeholder="同时作为登录账号" /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="createMemberForm.name" maxlength="40" /></el-form-item>
      <el-form-item label="所属部门">
        <el-select v-model="createMemberForm.departmentId" filterable >
          <el-option v-for="d in flatDepts" :key="d.id" :label="d.indentLabel" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="岗位/角色"><el-input v-model="createMemberForm.roleName" maxlength="30" placeholder="如：检测员、审核员" /></el-form-item>
      <el-form-item label="初始权限">
        <span class="text-muted">默认无功能和项目权限；创建后按部门授权上限分配。</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createMemberOpen = false">取消</el-button>
      <el-button type="primary" :loading="creatingMember" @click="createMember">创建人员</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="adjustMemberOpen" title="人员调整" width="560px" destroy-on-close>
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="调整部门后，功能和项目权限会自动收敛到新部门授权范围；不会更改人员账号 ID 和历史业务记录。"
    />
    <el-form label-width="100px" >
      <el-form-item label="人员编号"><el-input :model-value="adjustMemberForm.account" disabled /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="adjustMemberForm.name" maxlength="40" /></el-form-item>
      <el-form-item label="所属部门">
        <el-select v-model="adjustMemberForm.departmentId" filterable >
          <el-option v-for="d in flatDepts" :key="d.id" :label="d.indentLabel" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="岗位/角色"><el-input v-model="adjustMemberForm.roleName" maxlength="30" /></el-form-item>
      <el-form-item label="账号状态"><el-switch v-model="adjustMemberForm.enabled" active-text="启用" inactive-text="停用" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="adjustMemberOpen = false">取消</el-button>
      <el-button type="primary" :loading="adjustingMember" @click="saveMemberAdjustment">保存调整</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="deptOpen" :title="deptEditing ? '修改部门' : '添加部门'" width="460px">
    <el-form label-width="90px">
      <el-form-item label="部门名称"><el-input v-model="deptForm.name" /></el-form-item>
      <el-form-item label="上级部门">
        <el-select v-model="deptForm.parentId" clearable filterable placeholder="顶级（无上级）" >
          <el-option v-for="d in flatDepts" :key="d.id" :label="d.indentLabel" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="地点"><el-input v-model="deptForm.site" placeholder="总部 / 示例站点E …" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="deptOpen = false">取消</el-button>
      <el-button type="primary" :loading="deptSaving" @click="saveDept">保存</el-button>
    </template>
  </el-dialog>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import ErpPermissionEditor from '../../platformUi/finance/ErpPermissionEditor.vue'
// BEGIN TEMPLATE ORGANIZATION IMPORTS
import DataTable from '../../platformUi/TemplateDataTable'
// END TEMPLATE ORGANIZATION IMPORTS

import { SecurityAdminPanel } from '@/services/loginSecurityUi'
import { computed, ref, watch } from 'vue'
import { BASIC_PROJECT_PERMISSIONS, basicRoleEnabled, isDepartmentBasicRole, setBasicRoleEnabled } from '@/data/basicProjectAuthorization'
import { useRoute } from 'vue-router'
import ProjectAuthorizationFilters from '@/components/ProjectAuthorizationFilters.vue'
import { emptyProjectFilter, filterAuthorizationProjects, selectFilteredIds, templateFunctionUnion } from '@/data/projectAuthorizationFilter'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import PermissionMenuChecklist from '@/components/PermissionMenuChecklist.vue'
import {
  ADMIN_AVAILABLE,
  createPermissionTemplate,
  applyPermissionAppointmentWorkbook,
  createUser,
  createDepartment,
  deletePermissionTemplate,
  deleteDepartment,
  exportPermissionWorkbook,
  fetchOrgMembers,
  fetchOrgTree,
  getDepartmentAuthorizations,
  getMemberAuthorizations,
  importPermissionWorkbook,
  listPermissionTemplates,
  previewPermissionAppointmentWorkbook,
  resetUserPassword,
  revokeGrant,
  setGrant,
  updateDepartment,
  updateDepartmentAuthorizations,
  updateMemberAuthorizations,
  updatePermissionTemplate,
  updateUser,
  type DataGrant,
  type OrgAuthorization,
  type OrgMember,
  type OrgNode,
  type PermissionTemplate,
  type PermissionTemplateCatalog,
  type PermissionAppointmentPreview,
} from '@/services/admin'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'

type SwitchVal = string | number | boolean
const emptyAuth = (): OrgAuthorization => ({
  department: { id: 0, name: '' },
  permissions: [],
  projects: [],
  stepColumns: [],
  allowedProjectStepIds: [],
  selectedPermissionCodes: [],
  selectedProjectIds: [],
  selectedProjectStepIds: [],
  orgWide: false,
})
const emptyPermissionTemplateCatalog = (): PermissionTemplateCatalog => ({
  rows: [],
  permissions: [],
  projects: [],
  stepColumns: [],
  allowedProjectStepIds: [],
})
type StepColumn = OrgAuthorization['stepColumns'][number]
function hasStep(selected: number[], stepId: number | null) {
  return stepId !== null && selected.includes(stepId)
}
function setStep(selected: number[], stepId: number | null, checked: boolean) {
  if (stepId === null) return
  const index = selected.indexOf(stepId)
  if (checked && index < 0) selected.push(stepId)
  if (!checked && index >= 0) selected.splice(index, 1)
}

const route = useRoute()
const available = ADMIN_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '组织机构'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'org'))
const moduleKey = computed(() => route.meta.moduleKey ?? 'system')
const pages = computed(() => modules.find((m) => m.key === moduleKey.value)?.pages ?? [])

const tree = ref<OrgNode[]>([])
const currentDept = ref<OrgNode | null>(null)
const members = ref<OrgMember[]>([])
const movingUserId = ref<number | null>(null)
const resettingUserId = ref<number | null>(null)
const createMemberOpen = ref(false)
const creatingMember = ref(false)
const createMemberForm = ref({ account: '', name: '', departmentId: null as number | null, roleName: '' })
const adjustMemberOpen = ref(false)
const adjustingMember = ref(false)
const adjustMemberForm = ref({
  id: 0,
  account: '',
  name: '',
  departmentId: null as number | null,
  roleName: '',
  enabled: true,
})
interface FlatDept { id: number; indentLabel: string }
const flatDepts = computed(() => {
  const out: FlatDept[] = []
  const walk = (nodes: OrgNode[], depth: number) => nodes.forEach((node) => {
    out.push({ id: node.id, indentLabel: '　'.repeat(depth) + node.name })
    if (node.children?.length) walk(node.children, depth + 1)
  })
  walk(tree.value, 0)
  return out
})
const deptCount = computed(() => flatDepts.value.length)

const deptAuth = ref<OrgAuthorization>(emptyAuth())
const deptPermissionCodes = ref<string[]>([])
const deptProjectIds = ref<number[]>([])
const deptAuthTab = ref('function')
const deptAuthSaving = ref(false)
const deptProjectKeyword = ref('')
const deptProjectFilter = ref(emptyProjectFilter())
const filteredDeptProjects = computed(() => filterAuthorizationProjects(deptAuth.value.projects, deptProjectFilter.value, deptProjectKeyword.value))
function selectFilteredDeptProjects(checked: boolean) {
  deptProjectIds.value = selectFilteredIds(deptProjectIds.value, filteredDeptProjects.value.map(p => p.id), checked)
}

async function loadTree(keepDeptId?: number) {
  tree.value = await fetchOrgTree()
  if (keepDeptId && flatDepts.value.some((item) => item.id === keepDeptId)) await selectDept(keepDeptId)
}
async function selectDept(id: number) {
  if (currentDept.value?.id !== id) { deptProjectFilter.value = emptyProjectFilter(); deptProjectKeyword.value = '' }
  const [memberResult, authResult] = await Promise.all([
    fetchOrgMembers(id),
    getDepartmentAuthorizations(id),
  ])
  currentDept.value = { id: memberResult.department.id, name: memberResult.department.name } as OrgNode
  members.value = memberResult.rows
  deptAuth.value = authResult
  deptPermissionCodes.value = [...authResult.selectedPermissionCodes]
  deptProjectIds.value = [...authResult.selectedProjectIds]
}
function onNodeClick(node: OrgNode) { void selectDept(node.id) }
async function saveDepartmentAuth() {
  if (!currentDept.value) return
  deptAuthSaving.value = true
  try {
    const result = await updateDepartmentAuthorizations(currentDept.value.id, {
      permissionCodes: deptPermissionCodes.value,
      projectIds: deptProjectIds.value,
    })
    deptAuth.value = result
    deptPermissionCodes.value = [...result.selectedPermissionCodes]
    deptProjectIds.value = [...result.selectedProjectIds]
    await selectDept(currentDept.value.id)
    ElMessage.success('部门授权已保存')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存部门授权失败')
  } finally {
    deptAuthSaving.value = false
  }
}

const permissionTemplateOpen = ref(false)
const permissionTemplateEditorOpen = ref(false)
const permissionTemplatesLoading = ref(false)
const permissionTemplateSaving = ref(false)
const permissionExporting = ref(false)
const permissionImporting = ref(false)
const permissionImportInput = ref<HTMLInputElement | null>(null)
const appointmentImportInput = ref<HTMLInputElement | null>(null)
const appointmentPreviewOpen = ref(false)
const appointmentPreviewLoading = ref(false)
const appointmentApplying = ref(false)
const appointmentPreview = ref<PermissionAppointmentPreview | null>(null)
const appointmentFile = ref<File | null>(null)
const permissionTemplateCatalog = ref<PermissionTemplateCatalog>(emptyPermissionTemplateCatalog())
const permissionTemplateTab = ref('function')
const permissionTemplateProjectKeyword = ref('')
const permissionTemplateForm = ref({
  id: 0,
  code: '',
  name: '',
  description: '',
  enabled: true,
  permissionCodes: [] as string[],
  projectStepIds: [] as number[],
})
const enabledPermissionTemplates = computed(() =>
  permissionTemplateCatalog.value.rows.filter((item) => item.enabled),
)
const filteredPermissionTemplateProjects = computed(() => {
  const keyword = permissionTemplateProjectKeyword.value.trim().toLowerCase()
  if (!keyword) return permissionTemplateCatalog.value.projects
  return permissionTemplateCatalog.value.projects.filter((item) =>
    `${item.name} ${item.code} ${item.department}`.toLowerCase().includes(keyword),
  )
})

async function loadPermissionTemplates() {
  permissionTemplatesLoading.value = true
  try {
    permissionTemplateCatalog.value = await listPermissionTemplates()
  } finally {
    permissionTemplatesLoading.value = false
  }
}

async function openPermissionTemplateCenter() {
  permissionTemplateOpen.value = true
  try {
    await loadPermissionTemplates()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载权限模板失败')
  }
}

function openPermissionTemplateEditor(template?: PermissionTemplate) {
  permissionTemplateForm.value = template ? {
    id: template.id,
    code: template.code,
    name: template.name,
    description: template.description,
    enabled: template.enabled,
    permissionCodes: [...template.permissionCodes],
    projectStepIds: [...template.projectStepIds],
  } : {
    id: 0,
    code: '',
    name: '',
    description: '',
    enabled: true,
    permissionCodes: [],
    projectStepIds: [],
  }
  permissionTemplateTab.value = 'function'
  permissionTemplateProjectKeyword.value = ''
  permissionTemplateEditorOpen.value = true
}

function canSelectTemplateStep(stepId: number | null, step: StepColumn) {
  if (stepId === null || !permissionTemplateCatalog.value.allowedProjectStepIds.includes(stepId)) return false
  return (
    step.requiredPermissionCodes.length === 0
    || step.requiredPermissionCodes.some((code) => permissionTemplateForm.value.permissionCodes.includes(code))
  )
}
function selectablePermissionTemplateStepIds() {
  const ids: number[] = []
  permissionTemplateCatalog.value.projects.forEach((project) => {
    project.stepIds.forEach((stepId, index) => {
      const step = permissionTemplateCatalog.value.stepColumns[index]
      if (step && stepId !== null && canSelectTemplateStep(stepId, step)) ids.push(stepId)
    })
  })
  return [...new Set(ids)]
}
function selectAllPermissionTemplateSteps() {
  permissionTemplateForm.value.projectStepIds = selectablePermissionTemplateStepIds()
}
watch(
  () => permissionTemplateForm.value.permissionCodes,
  () => {
    const allowed = new Set(selectablePermissionTemplateStepIds())
    permissionTemplateForm.value.projectStepIds = permissionTemplateForm.value.projectStepIds.filter(
      (id) => allowed.has(id),
    )
  },
  { deep: true },
)

async function savePermissionTemplate() {
  const form = permissionTemplateForm.value
  if (!form.code.trim() || !form.name.trim()) {
    ElMessage.warning('请填写模板编码和模板名称')
    return
  }
  permissionTemplateSaving.value = true
  try {
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      enabled: form.enabled,
      permissionCodes: form.permissionCodes,
      projectStepIds: form.projectStepIds,
    }
    const saved = form.id
      ? await updatePermissionTemplate(form.id, payload)
      : await createPermissionTemplate(payload)
    permissionTemplateEditorOpen.value = false
    await loadPermissionTemplates()
    if (saved.syncSummary) {
      const sync = saved.syncSummary
      const message = `模板已保存，已同步 ${sync.assignedUserCount} 名关联人员，其中 ${sync.updatedUserCount} 名权限发生变化；项目授权未改动`
      if (sync.departmentLimitedUserCount) {
        ElMessage.warning(`${message}。${sync.departmentLimitedUserCount} 名人员的部分模板权限受部门上限限制`)
      } else {
        ElMessage.success(message)
      }
    } else {
      ElMessage.success('权限模板已保存')
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存权限模板失败')
  } finally {
    permissionTemplateSaving.value = false
  }
}

async function removePermissionTemplate(template: PermissionTemplate) {
  try {
    await ElMessageBox.confirm(
      `确认删除权限模板“${template.name}（${template.code}）”？已套用到人员的实际权限不会被删除。`,
      '删除权限模板',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    await deletePermissionTemplate(template.id)
    await loadPermissionTemplates()
    ElMessage.success('权限模板已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error instanceof Error ? error.message : '删除权限模板失败')
    }
  }
}

async function exportPermissionExcel() {
  permissionExporting.value = true
  try {
    await exportPermissionWorkbook()
    ElMessage.success('已导出权限模板和全部人员实际权限')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    permissionExporting.value = false
  }
}
function selectPermissionExcel() {
  permissionImportInput.value?.click()
}
async function handlePermissionExcel(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    await ElMessageBox.confirm(
      '导入会用 Excel 中的内容全量替换所有权限模板和所有人员实际功能/项目环节权限。系统会先完整校验，任何错误都不会写入。确认继续？',
      'Excel 全量替换',
      { type: 'warning', confirmButtonText: '校验并替换', cancelButtonText: '取消' },
    )
    permissionImporting.value = true
    const result = await importPermissionWorkbook(file)
    await loadPermissionTemplates()
    if (currentDept.value) await selectDept(currentDept.value.id)
    ElMessage.success(`替换完成：${result.templateCount} 个模板，${result.userCount} 名人员`)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error instanceof Error ? error.message : '导入失败')
    }
  } finally {
    permissionImporting.value = false
  }
}

function selectAppointmentExcel() {
  appointmentImportInput.value?.click()
}
async function handleAppointmentExcel(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  appointmentPreviewLoading.value = true
  try {
    const result = await previewPermissionAppointmentWorkbook(file)
    appointmentFile.value = file
    appointmentPreview.value = result
    appointmentPreviewOpen.value = true
    ElMessage.success('任命表预检完成，尚未写入数据库')
  } catch (error) {
    appointmentFile.value = null
    appointmentPreview.value = null
    ElMessage.error(error instanceof Error ? error.message : '任命表预检失败')
  } finally {
    appointmentPreviewLoading.value = false
  }
}
async function applyAppointmentImport() {
  if (!appointmentFile.value || !appointmentPreview.value) return
  appointmentApplying.value = true
  try {
    const result = await applyPermissionAppointmentWorkbook(
      appointmentFile.value,
      appointmentPreview.value.sourceSha256,
      appointmentPreview.value.previewToken,
    )
    appointmentPreview.value = result
    appointmentPreviewOpen.value = false
    await loadPermissionTemplates()
    if (currentDept.value) await selectDept(currentDept.value.id)
    ElMessage.success(`已更新 ${result.matchedPeopleCount} 人、${result.grantCount} 项项目环节授权`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任命表导入失败')
  } finally {
    appointmentApplying.value = false
  }
}

const memberErpRoles = ref<string[]>([])
const memberSealedReportDownload = ref(false)
const memberReportDistribution = ref(false)
const memberEquipmentDepartmentIds = ref<number[]>([])
const memberCorrectionApproval = ref(false)
const memberSealConfirmation = ref(false)
const memberAuthOpen = ref(false)
const memberAuth = ref<OrgAuthorization>(emptyAuth())
const memberPermissionCodes = ref<string[]>([])
const memberProjectStepIds = ref<number[]>([])
const memberAuthTab = ref('function')
const memberAuthSaving = ref(false)
const memberProjectKeyword = ref('')
const memberProjectFilter = ref(emptyProjectFilter())
const memberTemplateIds = ref<number[]>([])
const memberActiveRoleCode = ref('')
const memberScopeType = ref('')
function memberIsBasicRole(role: string) { return isDepartmentBasicRole(memberScopeType.value, role) }
function memberBasicEnabled(role: string) { return basicRoleEnabled(memberPermissionCodes.value, role) }
function memberBasicAllowed(role: string) { return memberAuth.value.permissions.some(p => p.code === BASIC_PROJECT_PERMISSIONS[role]) }
function toggleMemberBasicRole(role: string, enabled: boolean) {
  memberPermissionCodes.value = setBasicRoleEnabled(memberPermissionCodes.value, role, enabled, memberAuth.value.permissions.map(p => p.code))
}
const memberRoleLabels: Record<string, string> = {
  entrust_register: '委托登记',
  entrust_review: '合同评审',
  sample_inbound: '样品入库',
  sample_outbound: '样品出库',
  data_entry: '主检',
  report_review: '报告审核',
  report_approval: '报告批准',
  report_print: '报告签发',
  report_archive: '报告归档',
}
const memberRoleSteps = computed(() => memberAuth.value.stepColumns.filter((step) => (
  memberIsBasicRole(step.code)
  || step.requiredPermissionCodes.length === 0
  || step.requiredPermissionCodes.some((code) => memberPermissionCodes.value.includes(code))
)))
const memberActiveRole = computed(() => (
  memberRoleSteps.value.find((step) => step.code === memberActiveRoleCode.value) ?? null
))
const filteredMemberProjects = computed(() => filterAuthorizationProjects(memberAuth.value.projects, memberProjectFilter.value, memberProjectKeyword.value))
function memberRoleLabel(role: StepColumn) {
  return memberRoleLabels[role.code] ?? role.name
}
function memberProjectRoleStepId(project: OrgAuthorization['projects'][number], roleCode: string) {
  const index = memberAuth.value.stepColumns.findIndex((step) => step.code === roleCode)
  return index < 0 ? null : project.stepIds[index] ?? null
}
function memberRoleStepIds(roleCode: string, projects = memberAuth.value.projects) {
  return projects
    .map((project) => memberProjectRoleStepId(project, roleCode))
    .filter((stepId): stepId is number => stepId !== null)
}
function memberRoleSelectedCount(roleCode: string) {
  const selected = new Set(memberProjectStepIds.value)
  return memberRoleStepIds(roleCode).filter((stepId) => selected.has(stepId)).length
}
const visibleMemberRoleStepIds = computed(() => (
  memberActiveRole.value ? memberRoleStepIds(memberActiveRole.value.code, filteredMemberProjects.value) : []
))
const someVisibleProjectsSelectedForRole = computed(() => (
  visibleMemberRoleStepIds.value.some((stepId) => memberProjectStepIds.value.includes(stepId))
))
const allVisibleProjectsSelectedForRole = computed(() => (
  visibleMemberRoleStepIds.value.length > 0
  && visibleMemberRoleStepIds.value.every((stepId) => memberProjectStepIds.value.includes(stepId))
))
function toggleAllVisibleProjectsForRole(checked: boolean) {
  memberProjectStepIds.value = selectFilteredIds(memberProjectStepIds.value, visibleMemberRoleStepIds.value, checked)
}
function selectAllVisibleProjectsForRole() {
  toggleAllVisibleProjectsForRole(true)
}
async function openMemberAuth(member: OrgMember, tab = 'function') {
  if (!currentDept.value) return
  try {
    const [result, templates] = await Promise.all([
      getMemberAuthorizations(currentDept.value.id, member.id),
      listPermissionTemplates(),
    ])
    permissionTemplateCatalog.value = templates
    memberScopeType.value = member.dataScope.scopeType
    memberAuth.value = {
      ...result,
      projects: templates.projects,
      stepColumns: templates.stepColumns,
      allowedProjectStepIds: templates.allowedProjectStepIds,
    }
    memberErpRoles.value = [...(result.erpAuthorization?.roles ?? [])]
    memberCorrectionApproval.value = result.correctionApproval === true
    memberSealConfirmation.value = result.sealConfirmation === true
    memberSealedReportDownload.value = result.sealedReportDownload === true || result.reportDeliveryInherited === true
    memberReportDistribution.value = result.reportDistribution === true || result.reportDeliveryInherited === true
    memberEquipmentDepartmentIds.value = [...(result.equipmentDepartmentIds ?? [])]
    memberAuthTab.value = tab
    memberPermissionCodes.value = [...result.selectedPermissionCodes]
    memberProjectStepIds.value = [...result.selectedProjectStepIds]
    memberTemplateIds.value = [...(result.selectedTemplateIds ?? [])]
    memberProjectKeyword.value = ''
    memberProjectFilter.value = emptyProjectFilter()
    memberActiveRoleCode.value = memberRoleSteps.value[0]?.code ?? ''
    memberAuthOpen.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载人员授权失败')
  }
}
function applySelectedTemplates() {
  const selected = permissionTemplateCatalog.value.rows.filter(
    (item) => item.enabled && memberTemplateIds.value.includes(item.id),
  )
  const permissionUnion = new Set(selected.flatMap((item) => item.permissionCodes))
  const allowedPermissionCodes = new Set(memberAuth.value.permissions.map((item) => item.code))
  memberPermissionCodes.value = templateFunctionUnion(memberPermissionCodes.value, selected, [...allowedPermissionCodes])
  const clipped = [...permissionUnion].filter(code => !allowedPermissionCodes.has(code)).length
  ElMessage.success(
    clipped > 0
      ? `已填充功能权限，${clipped} 项超出部门上限未套用；项目授权未改动`
      : `已按 ${selected.length} 个模板填充功能权限；项目授权未改动`,
  )
}
async function saveMemberAuth() {
  if (!currentDept.value || !memberAuth.value.user) return
  memberAuthSaving.value = true
  try {
    await updateMemberAuthorizations(currentDept.value.id, memberAuth.value.user.id, {
      permissionCodes: memberPermissionCodes.value,
      projectStepIds: memberProjectStepIds.value,
      templateIds: memberTemplateIds.value,
      expandProjectScope: true,
      equipmentDepartmentIds: memberEquipmentDepartmentIds.value,
      correctionApproval: memberCorrectionApproval.value,
      sealConfirmation: memberSealConfirmation.value,
      ...(!memberAuth.value.reportDeliveryInherited ? { sealedReportDownload: memberSealedReportDownload.value, reportDistribution: memberReportDistribution.value } : {}),
      ...(memberAuth.value.erpAuthorization?.canManage ? { erpPermissions: memberErpRoles.value } : {}),
    })
    memberAuthOpen.value = false
    await selectDept(currentDept.value.id)
    ElMessage.success('人员授权已保存')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存人员授权失败')
  } finally {
    memberAuthSaving.value = false
  }
}
// Template application changes functions only. Never silently clear project drafts.
// The backend continues to enforce function prerequisites when authorizations save.
watch(memberRoleSteps, (roles) => {
  if (!roles.some((role) => role.code === memberActiveRoleCode.value)) {
    memberActiveRoleCode.value = roles[0]?.code ?? ''
  }
})

async function moveMember(member: OrgMember, departmentId: number) {
  if (departmentId === member.departmentId) return
  const target = flatDepts.value.find((item) => item.id === departmentId)
  if (!target) return
  try {
    await ElMessageBox.confirm(
      `确认将「${member.name}」调整到「${target.indentLabel.trim()}」？人员功能和项目权限会自动收敛到新部门授权范围。`,
      '调整人员部门',
      { type: 'warning', confirmButtonText: '确认调整', cancelButtonText: '取消' },
    )
    movingUserId.value = member.id
    await updateUser(member.id, { departmentId })
    await loadTree(currentDept.value?.id)
    ElMessage.success('人员部门及授权范围已同步')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '部门调整失败')
  } finally {
    movingUserId.value = null
  }
}

function openCreateMember() {
  createMemberForm.value = {
    account: '',
    name: '',
    departmentId: currentDept.value?.id ?? null,
    roleName: '',
  }
  createMemberOpen.value = true
}

async function createMember() {
  const form = createMemberForm.value
  const account = form.account.trim()
  const name = form.name.trim()
  if (!account || !name || !form.departmentId) {
    ElMessage.warning('请填写人员编号、姓名和所属部门')
    return
  }
  if (!/^[A-Za-z0-9_.-]{2,40}$/.test(account)) {
    ElMessage.warning('人员编号仅支持字母、数字、点、下划线和短横线')
    return
  }
  creatingMember.value = true
  try {
    const result = await createUser({
      account,
      name,
      departmentId: form.departmentId,
      roleName: form.roleName.trim() || '自定义角色',
      personnel: { position: form.roleName.trim() },
    })
    createMemberOpen.value = false
    await loadTree(form.departmentId)
    await ElMessageBox.alert(
      `人员和登录账号已建立。\n账号：${result.user.account}\n临时密码：${result.tempPassword}\n首次登录必须修改密码。`,
      '新建人员成功',
      { confirmButtonText: '我已记录', type: 'success' },
    )
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '新建人员失败')
  } finally {
    creatingMember.value = false
  }
}

function openAdjustMember(member: OrgMember) {
  adjustMemberForm.value = {
    id: member.id,
    account: member.account,
    name: member.name,
    departmentId: member.departmentId,
    roleName: member.roleName,
    enabled: member.enabled,
  }
  adjustMemberOpen.value = true
}

async function saveMemberAdjustment() {
  const form = adjustMemberForm.value
  if (!form.name.trim() || !form.departmentId) {
    ElMessage.warning('请填写姓名和所属部门')
    return
  }
  adjustingMember.value = true
  try {
    await updateUser(form.id, {
      name: form.name.trim(),
      departmentId: form.departmentId,
      roleName: form.roleName.trim() || '自定义角色',
      enabled: form.enabled,
      personnel: { position: form.roleName.trim() },
    })
    adjustMemberOpen.value = false
    await loadTree(form.departmentId)
    ElMessage.success('人员基本信息、部门和账号状态已同步')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '人员调整失败')
  } finally {
    adjustingMember.value = false
  }
}

async function resetMemberPassword(member: OrgMember) {
  try {
    await ElMessageBox.confirm(
      `确认将「${member.name}（${member.account}）」的密码重置为“账号＋随机五位数字”的初始密码？重置后将显示新生成的初始密码，该账户下次登录必须修改密码。`,
      '重置用户密码',
      { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' },
    )
    resettingUserId.value = member.id
    const result = await resetUserPassword(member.id)
    ElMessage.success(`密码已重置为：${result.tempPassword}`)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error instanceof Error ? error.message : '重置密码失败')
    }
  } finally {
    resettingUserId.value = null
  }
}

const dataGrantOpen = ref(false)
const dataGrantUser = ref<OrgMember | null>(null)
const addGrantForm = ref({ departmentId: null as number | null, seeData: true, seeMembers: true, includeChildren: false })
function openDataGrant(member: OrgMember) {
  dataGrantUser.value = member
  addGrantForm.value = { departmentId: null, seeData: true, seeMembers: true, includeChildren: false }
  dataGrantOpen.value = true
}
async function refreshDataGrantUser() {
  if (!currentDept.value || !dataGrantUser.value) return
  const id = dataGrantUser.value.id
  const result = await fetchOrgMembers(currentDept.value.id)
  members.value = result.rows
  dataGrantUser.value = members.value.find((item) => item.id === id) ?? null
}
async function saveDataGrant(departmentId: number, grant: DataGrant) {
  if (!dataGrantUser.value) return
  await setGrant(dataGrantUser.value.id, { departmentId, seeData: grant.seeData, seeMembers: grant.seeMembers, includeChildren: grant.includeChildren })
  await refreshDataGrantUser()
  ElMessage.success('数据授权已保存')
}
async function addDataGrant() {
  if (!dataGrantUser.value || !addGrantForm.value.departmentId) return
  await setGrant(dataGrantUser.value.id, {
    departmentId: addGrantForm.value.departmentId,
    seeData: addGrantForm.value.seeData,
    seeMembers: addGrantForm.value.seeMembers,
    includeChildren: addGrantForm.value.includeChildren,
  })
  addGrantForm.value = { departmentId: null, seeData: true, seeMembers: true, includeChildren: false }
  await refreshDataGrantUser()
  ElMessage.success('已增加数据授权')
}
async function revokeDataGrant(departmentId: number) {
  if (!dataGrantUser.value) return
  await revokeGrant(dataGrantUser.value.id, departmentId)
  await refreshDataGrantUser()
  ElMessage.success('数据授权已收回')
}

const deptOpen = ref(false)
const deptEditing = ref(false)
const deptSaving = ref(false)
const deptForm = ref({ name: '', parentId: null as number | null, site: '总部' })
function openAddDept() {
  deptEditing.value = false
  deptForm.value = { name: '', parentId: currentDept.value?.id ?? null, site: '总部' }
  deptOpen.value = true
}
function findNode(nodes: OrgNode[], id: number): OrgNode | null {
  for (const node of nodes) {
    if (node.id === id) return node
    const found = node.children ? findNode(node.children, id) : null
    if (found) return found
  }
  return null
}
function openEditDept() {
  if (!currentDept.value) return
  const node = findNode(tree.value, currentDept.value.id)
  deptEditing.value = true
  deptForm.value = { name: node?.name ?? currentDept.value.name, parentId: node?.parentId ?? null, site: node?.site ?? '' }
  deptOpen.value = true
}
async function saveDept() {
  if (!deptForm.value.name.trim()) { ElMessage.warning('部门名称必填'); return }
  deptSaving.value = true
  try {
    if (deptEditing.value && currentDept.value) await updateDepartment(currentDept.value.id, deptForm.value)
    else await createDepartment(deptForm.value)
    deptOpen.value = false
    await loadTree(currentDept.value?.id)
    ElMessage.success('部门已保存')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存部门失败')
  } finally {
    deptSaving.value = false
  }
}
async function removeDept() {
  if (!currentDept.value) return
  try {
    await ElMessageBox.confirm(`确认删除部门「${currentDept.value.name}」？`, '删除部门', { type: 'warning' })
    await deleteDepartment(currentDept.value.id)
    currentDept.value = null
    members.value = []
    deptAuth.value = emptyAuth()
    await loadTree()
    ElMessage.success('部门已删除')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error instanceof Error ? error.message : '删除部门失败')
  }
}

if (available) {
  loadTree().catch((error) => ElMessage.error(error instanceof Error ? error.message : '加载组织机构失败'))
}

// BEGIN TEMPLATE ORGANIZATION ADAPTER
const departmentColumns=[{key:'name' as const,label:'部门名称'},{key:'memberCount' as const,label:'人数'}]
const departmentRows=computed(()=>{const rows:(OrgNode & {indentLabel:string})[]=[];const visit=(nodes:OrgNode[],depth:number)=>nodes.forEach(node=>{rows.push({...node,indentLabel:'　'.repeat(depth)+node.name});visit(node.children||[],depth+1)});visit(tree.value,0);return rows})
// END TEMPLATE ORGANIZATION ADAPTER
</script>


