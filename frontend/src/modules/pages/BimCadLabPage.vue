<template>
  <ModuleWorkspace
    title="BIM/CAD 智能识别实验"
    area-name="BIM/CAD实验功能"
    module-name="图纸识别与模拟"
    description="上传 CAD 导出图、扫描 PDF 或图纸照片，人工复核识别结果后进行实验性计算模拟。"
    variant="experiment"
    :show-command="false"
    :show-content="false"
  >
  <section >
    <header >
      <div>
        <div ><span>实验功能</span> BIM / CAD 智能识别</div>
        <p>识别墙体、窗和门；人工校核比例与参数后进行简化计算模拟。</p>
      </div>
      <div  :class="status?.ready ? 'text-success' : 'text-warning'">
        <strong>{{ status?.ready ? '实验引擎就绪' : '实验引擎未就绪' }}</strong>
        <span>{{ status?.model ?? '正在检查模型' }}</span>
      </div>
    </header>

    <el-alert
      title="研究验证用途：识别覆盖图、比例尺和计算参数必须人工复核；结果不形成检测结论，不写入正式报告或业务流程。"
      type="warning"
      show-icon
      :closable="false"
      
    />

    <div class="row g-3">
      <div class="col-12 col-md-6"><span>识别对象</span><strong>墙体 · 窗 · 门</strong></div>
      <div class="col-12 col-md-6"><span>研究样本指标</span><strong>{{ benchmarkLabel }}</strong></div>
      <div class="col-12 col-md-6"><span>文件处理</span><strong>请求内临时处理 · 不入业务库</strong></div>
      <div class="col-12 col-md-6"><span>支持格式</span><strong>PNG / JPG / WEBP / PDF</strong></div>
    </div>

    <el-steps :active="activeStep" finish-status="success" align-center >
      <el-step title="上传图纸" description="CAD 导出图或照片" />
      <el-step title="AI 识别" description="墙、窗、门覆盖图" />
      <el-step title="人工校核" description="比例、面积与参数" />
      <el-step title="计算模拟" description="实验性估算结果" />
    </el-steps>

    <div class="row g-3">
      <el-card class="col-12 col-md-6" shadow="never">
        <template #header>
          <div class="card-title"><span>01</span><div><strong>上传图纸</strong><small>文件不会进入正式附件库</small></div></div>
        </template>
        <el-upload
          drag
          :auto-upload="false"
          :show-file-list="false"
          accept=".png,.jpg,.jpeg,.webp,.pdf"
          :on-change="handleFileChange"
          :disabled="recognizing"
        >
          <el-icon ><UploadFilled /></el-icon>
          <div >拖入图纸，或<em>选择文件</em></div>
          <template #tip>
            <div class="text-muted small">单文件不超过 20MB。DWG/DXF 请先导出图片或 PDF；PDF 当前识别第 1 页。</div>
          </template>
        </el-upload>
        <div v-if="selectedFile" >
          <el-icon><Document /></el-icon>
          <div><strong>{{ selectedFile.name }}</strong><span>{{ formatBytes(selectedFile.size) }}</span></div>
          <el-button text type="danger" :disabled="recognizing" @click="resetAll">移除</el-button>
        </div>
        <div >
          <span>预处理方式</span>
          <el-radio-group v-model="preprocessing" size="small">
            <el-radio-button value="auto">自动清理标注</el-radio-button>
            <el-radio-button value="none">保留原图</el-radio-button>
          </el-radio-group>
        </div>
        <el-button
          type="primary"
          
          :loading="recognizing"
          :disabled="!selectedFile || !status?.ready"
          @click="runRecognition"
        >
          开始识别
        </el-button>
        <p v-if="status && !status.ready" >{{ status.modelError || '模型依赖尚未准备完成' }}</p>
      </el-card>

      <el-card class="col-12 col-md-6" shadow="never">
        <template #header>
          <div class="card-title"><span>02</span><div><strong>识别覆盖图</strong><small>红色墙体、蓝色窗、绿色门</small></div></div>
        </template>
        <div v-if="!recognition" >
          <el-icon><PictureRounded /></el-icon>
          <strong>等待识别结果</strong>
          <span>上传图纸并运行识别后，可在这里对照原图和覆盖图。</span>
        </div>
        <template v-else>
          <el-tabs v-model="previewTab" >
            <el-tab-pane label="识别覆盖图" name="overlay">
              <img :src="recognition.preview.overlay" alt="图纸识别覆盖图" />
            </el-tab-pane>
            <el-tab-pane label="处理原图" name="original">
              <img :src="recognition.preview.original" alt="上传图纸处理预览" />
            </el-tab-pane>
          </el-tabs>
          <div class="text-muted small">
            <span>耗时 {{ recognition.elapsedSeconds }} 秒</span>
            <span>{{ recognition.source.processedWidth }} × {{ recognition.source.processedHeight }} px</span>
            <span v-if="recognition.source.pdfPageCount">PDF 共 {{ recognition.source.pdfPageCount }} 页，本次第 1 页</span>
          </div>
        </template>
      </el-card>
    </div>

    <template v-if="recognition">
      <div class="row g-3">
        <div v-for="item in componentMetrics" :key="item.key" class="col-12 col-md-6" >
          <span>{{ item.label }}</span>
          <strong>{{ item.components }} <small>个构件</small></strong>
          <em>像素占比 {{ item.percentage }}%</em>
        </div>
      </div>

      <el-card  shadow="never">
        <template #header>
          <div class="card-title"><span>03</span><div><strong>人工校核与模拟参数</strong><small>AI 不自动确认比例尺和工程参数</small></div></div>
        </template>
        <el-form label-position="top" >
          <div class="h5 mb-3">几何与用途</div>
          <div class="row g-3">
            <el-form-item class="col-12 col-md-6" label="图纸比例（1 px 对应 mm）">
              <el-input-number v-model="parameters.scaleMmPerPixel" :min="0.1" :max="2000" :step="1" :precision="1" />
            </el-form-item>
            <el-form-item class="col-12 col-md-6" label="单层建筑面积（m²，可选人工覆盖）">
              <el-input-number v-model="parameters.floorAreaM2" :min="1" :max="1000000" :step="10" placeholder="不填则按图幅比例估算" />
            </el-form-item>
            <el-form-item class="col-12 col-md-6" label="地上层数">
              <el-input-number v-model="parameters.floors" :min="1" :max="200" />
            </el-form-item>
            <el-form-item class="col-12 col-md-6" label="层高（m）">
              <el-input-number v-model="parameters.floorHeight" :min="2" :max="20" :step="0.1" :precision="1" />
            </el-form-item>
            <el-form-item class="col-12 col-md-6" label="城市">
              <el-select v-model="parameters.city"><el-option v-for="item in cityOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
            </el-form-item>
            <el-form-item class="col-12 col-md-6" label="建筑类型">
              <el-select v-model="parameters.buildingType"><el-option v-for="item in buildingOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
            </el-form-item>
          </div>

          <el-collapse >
            <el-collapse-item title="围护结构与系统参数（高级）" name="advanced">
              <div class="row g-3">
                <el-form-item class="col-12 col-md-6" label="外墙 U 值"><el-input-number v-model="parameters.wallU" :min="0.05" :max="10" :step="0.1" /></el-form-item>
                <el-form-item class="col-12 col-md-6" label="外窗 U 值"><el-input-number v-model="parameters.windowU" :min="0.1" :max="15" :step="0.1" /></el-form-item>
                <el-form-item class="col-12 col-md-6" label="屋面 U 值"><el-input-number v-model="parameters.roofU" :min="0.05" :max="10" :step="0.1" /></el-form-item>
                <el-form-item class="col-12 col-md-6" label="地面 U 值"><el-input-number v-model="parameters.floorU" :min="0.05" :max="10" :step="0.1" /></el-form-item>
                <el-form-item class="col-12 col-md-6" label="外窗 SHGC"><el-input-number v-model="parameters.windowShgc" :min="0.05" :max="1" :step="0.05" /></el-form-item>
                <el-form-item class="col-12 col-md-6" label="年运行小时"><el-input-number v-model="parameters.operatingHours" :min="1" :max="8760" :step="100" /></el-form-item>
                <el-form-item class="col-12 col-md-6" label="供暖系统"><el-select v-model="parameters.heatingSystem"><el-option label="燃气锅炉" value="gas_boiler" /><el-option label="空气源热泵" value="heat_pump_air" /><el-option label="集中供暖" value="district" /><el-option label="无供暖" value="none" /></el-select></el-form-item>
                <el-form-item class="col-12 col-md-6" label="制冷系统"><el-select v-model="parameters.coolingSystem"><el-option label="分体空调" value="split_ac" /><el-option label="中央冷水机组" value="central_chiller" /><el-option label="VRV/VRF 多联机" value="vrv" /><el-option label="无制冷" value="none" /></el-select></el-form-item>
              </div>
            </el-collapse-item>
          </el-collapse>
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
            <el-button @click="resetParameters">恢复建议参数</el-button>
            <el-button type="primary" :loading="simulating" @click="runSimulation">运行计算模拟</el-button>
          </div>
        </el-form>
      </el-card>
    </template>

    <el-card v-if="simulation"  shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <div class="card-title"><span>04</span><div><strong>实验模拟结果</strong><small>{{ simulation.method }}</small></div></div>
          <el-button @click="downloadResult">下载实验结果 JSON</el-button>
        </div>
      </template>
      <div class="row g-3">
        <div class="col-12 col-md-6"><span>年综合能耗</span><strong>{{ formatNumber(simulation.result.summary.total_energy_kwh) }}</strong><em>kWh</em></div>
        <div class="col-12 col-md-6"><span>能耗强度 EUI</span><strong>{{ simulation.result.summary.eui }}</strong><em>kWh/(m²·a)</em></div>
        <div class="col-12 col-md-6"><span>实验分级</span><strong>{{ simulation.result.summary.rating }}</strong><em>{{ simulation.result.summary.rating_label }}</em></div>
        <div class="col-12 col-md-6"><span>总建筑面积</span><strong>{{ formatNumber(simulation.result.summary.total_floor_area_m2) }}</strong><em>m²</em></div>
      </div>
      <div class="row g-3">
        <div>
          <h3 class="h5 mb-3">分项能耗</h3>
          <div v-for="item in energyBreakdown" :key="item.key" >
            <span>{{ item.label }}</span>
            <el-progress :percentage="item.percentage" :stroke-width="10" :show-text="false" />
            <strong>{{ formatNumber(item.value) }} kWh</strong>
          </div>
        </div>
        <div >
          <h3 class="h5 mb-3">使用边界</h3>
          <p v-for="warning in simulation.warnings" :key="warning"><el-icon><Warning /></el-icon>{{ warning }}</p>
        </div>
      </div>
    </el-card>
  </section>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Document, PictureRounded, UploadFilled, Warning } from '@element-plus/icons-vue'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import {
  getBimCadStatus,
  recognizeBimCad,
  simulateBimCad,
  type BimCadRecognition,
  type BimCadSimulation,
  type BimCadStatus,
  type SimulationParameters,
} from '@/services/bimCad'

const status = ref<BimCadStatus>()
const selectedFile = ref<File>()
const preprocessing = ref('auto')
const recognizing = ref(false)
const simulating = ref(false)
const recognition = ref<BimCadRecognition>()
const simulation = ref<BimCadSimulation>()
const previewTab = ref('overlay')

const suggestedParameters: SimulationParameters = {
  scaleMmPerPixel: 10,
  floorAreaM2: null,
  floors: 1,
  floorHeight: 3,
  city: 'beijing',
  buildingType: 'office',
  orientation: 'south',
  heatingSystem: 'gas_boiler',
  coolingSystem: 'split_ac',
  wallU: 0.5,
  windowU: 2.4,
  roofU: 0.4,
  floorU: 0.5,
  windowShgc: 0.5,
  lightingPowerDensity: 8,
  equipmentPowerDensity: 12,
  operatingHours: 2500,
  ventilationRate: 0.5,
}
const parameters = reactive<SimulationParameters>({ ...suggestedParameters })

const cityOptions = [
  ['beijing', '北京 · 寒冷A区'], ['tianjin', '天津 · 寒冷A区'], ['shanghai', '上海 · 夏热冬冷'],
  ['chongqing', '重庆 · 夏热冬冷'], ['chengdu', '成都 · 夏热冬冷'], ['guangzhou', '广州 · 夏热冬暖'],
].map(([value, label]) => ({ value, label }))
const buildingOptions = [
  ['office', '办公建筑'], ['commercial', '商业建筑'], ['hotel', '酒店建筑'],
  ['hospital', '医院建筑'], ['school', '学校建筑'], ['residential', '居住建筑'],
].map(([value, label]) => ({ value, label }))

const activeStep = computed(() => simulation.value ? 4 : recognition.value ? 3 : selectedFile.value ? 1 : 0)
const benchmarkLabel = computed(() => status.value ? `mIoU ${status.value.modelBenchmark.value}` : '核验中')
const componentMetrics = computed(() => {
  if (!recognition.value) return []
  const stats = recognition.value.stats
  return [
    { key: 'wall', label: '墙体', components: recognition.value.metrics.wallComponents, percentage: stats['墙体']?.percentage ?? stats.wall?.percentage ?? 0, color: '#ef4444' },
    { key: 'window', label: '窗', components: recognition.value.metrics.windowComponents, percentage: stats['窗']?.percentage ?? stats.window?.percentage ?? 0, color: '#3b82f6' },
    { key: 'door', label: '门', components: recognition.value.metrics.doorComponents, percentage: stats['门']?.percentage ?? stats.door?.percentage ?? 0, color: '#22c55e' },
  ]
})
const energyLabels: Record<string, string> = { heating: '供暖', cooling: '制冷', lighting: '照明', equipment: '设备', ventilation: '通风', dhw: '生活热水' }
const energyBreakdown = computed(() => {
  const values = simulation.value?.result.breakdown_kwh ?? {}
  const max = Math.max(...Object.values(values), 1)
  return Object.entries(values).map(([key, value]) => ({ key, label: energyLabels[key] ?? key, value, percentage: Math.round(value / max * 100) }))
})

onMounted(async () => {
  try { status.value = await getBimCadStatus() }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '实验引擎状态检查失败') }
})

function handleFileChange(upload: UploadFile) {
  if (!upload.raw) return
  if (upload.raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('单个图纸文件不能超过 20MB')
    return
  }
  selectedFile.value = upload.raw
  recognition.value = undefined
  simulation.value = undefined
}

async function runRecognition() {
  if (!selectedFile.value) return
  recognizing.value = true
  try {
    recognition.value = await recognizeBimCad(selectedFile.value, preprocessing.value)
    simulation.value = undefined
    ElMessage.success('识别完成，请人工核对覆盖图和比例参数')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '图纸识别失败')
  } finally { recognizing.value = false }
}

async function runSimulation() {
  if (!recognition.value) return
  simulating.value = true
  try {
    simulation.value = await simulateBimCad(recognition.value, { ...parameters })
    ElMessage.success('实验模拟完成')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '计算模拟失败')
  } finally { simulating.value = false }
}

function resetParameters() { Object.assign(parameters, suggestedParameters) }
function resetAll() { selectedFile.value = undefined; recognition.value = undefined; simulation.value = undefined }
function formatBytes(value: number) { return value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB` }
function formatNumber(value: number) { return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value) }
function downloadResult() {
  if (!simulation.value || !recognition.value) return
  const content = JSON.stringify({ notice: '演示数据，仅供实验验证，不形成检测结论', recognition: { ...recognition.value, preview: undefined }, simulation: simulation.value }, null, 2)
  const url = URL.createObjectURL(new Blob([content], { type: 'application/json;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `BIM-CAD实验结果-${simulation.value.simulationId.slice(0, 8)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>


