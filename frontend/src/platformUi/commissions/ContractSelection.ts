import { computed, defineComponent, h, onBeforeUnmount, ref, watch, type PropType } from 'vue'
import { ElDialog } from '../controls'
import { fetchContractSelectionPage, type Agreement } from '@/services/pipeline'
import { useLiveSearch } from '@/composables/liveSearch'

export default defineComponent({
  name: 'ContractSelection',
  props: { modelValue: String, selected: Object as PropType<Agreement>, disabled: Boolean },
  emits: ['picked'],
  setup(props, { emit }) {
    const open = ref(false), keyword = ref(''), page = ref(1), total = ref(0)
    const rows = ref<Agreement[]>([]), pending = ref<Agreement>(), loading = ref(false), error = ref('')
    const scope = ref<'all' | 'department'>()
    const pages = computed(() => Math.max(1, Math.ceil(total.value / 20)))
    let revision = 0, request: AbortController | undefined
    const stop = () => { revision++; request?.abort(); loading.value = false }
    async function load() {
      stop()
      if (!open.value || props.disabled) return
      const current = revision, controller = new AbortController()
      request = controller; loading.value = true; error.value = ''; rows.value = []
      const timeout = setTimeout(() => controller.abort(), 12000)
      try {
        const result = await fetchContractSelectionPage(keyword.value.trim(), page.value, controller.signal)
        if (current !== revision || !open.value) return
        rows.value = result.rows; total.value = result.total; scope.value = result.scope || 'department'
      } catch (cause) {
        if (current === revision && open.value) {
          error.value = controller.signal.aborted ? '查询超时，请点击搜索重试' : cause instanceof Error ? cause.message : '合同加载失败，请重试'
        }
      } finally {
        clearTimeout(timeout)
        if (current === revision) loading.value = false
      }
    }
    watch(keyword, () => { stop(); rows.value = []; total.value = 0; page.value = 1 }, { flush: 'sync' })
    const search = useLiveSearch(keyword, load, () => open.value && !props.disabled)
    const label = (row?: Agreement) => row ? [row.agreementNo, row.client, row.projectName].filter(Boolean).join(' · ') : props.modelValue || ''
    function launch() {
      if (props.disabled) return
      keyword.value = ''; page.value = 1; total.value = 0; pending.value = props.selected; scope.value = undefined
      open.value = true; void load()
    }
    function close() { open.value = false; search.cancel(); stop() }
    function confirm() {
      if (!pending.value || props.disabled || loading.value || error.value) return
      emit('picked', pending.value); close()
    }
    watch(() => props.disabled, value => { if (value) close() })
    onBeforeUnmount(stop)
    const button = (text: string, action: () => void, disabled = false, primary = false) =>
      h('button', { type: 'button', class: `btn btn-${primary ? 'primary' : 'light'}`, onClick: action, disabled }, text)
    return () => h('div', { class: 'w-100' }, [
      h('div', { class: 'input-group' }, [
        h('input', { class: 'form-control', readonly: true, disabled: props.disabled, value: label(props.selected),
          placeholder: '请选择已完成登记的合同', 'aria-label': '已关联合同', onClick: launch }),
        button('选择合同', launch, props.disabled),
        props.modelValue ? button('清空', () => { if (!props.disabled) emit('picked', undefined) }, props.disabled) : null,
      ]),
      h(ElDialog, { modelValue: open.value, 'onUpdate:modelValue': (v: boolean) => { if (!v) close() },
        title: '选择合同', width: '1100px', closeOnClickModal: false }, {
        default: () => [
          h('p', { class: 'text-muted' }, (scope.value === 'all'
            ? '当前账号可选择全院所有已完成登记的合同，不受项目部门限制。'
            : scope.value === 'department'
              ? '仅显示已完成登记、项目部门（检测部门）为本人所属部门的合同。'
              : '查询可选择的已登记合同。') + '输入后自动筛选，也可点击搜索。'),
          h('form', { class: 'd-flex gap-2 mb-3', onSubmit: (e: Event) => { e.preventDefault(); search.run() } }, [
            h('input', { class: 'form-control', value: keyword.value, placeholder: '合同编号、客户名称或项目名称',
              'aria-label': '搜索合同', onInput: (e: Event) => { keyword.value = (e.target as HTMLInputElement).value } }),
            h('button', { type: 'submit', class: 'btn btn-primary flex-shrink-0' }, '搜索'),
          ]),
          h('div', { class: 'd-flex flex-wrap gap-2 mb-3' }, [
            h('span', { class: 'text-muted' }, `共 ${total.value} 条`),
            pending.value ? h('span', { class: 'badge bg-primary-transparent text-wrap text-start' }, `已选：${label(pending.value)}`) : null,
          ]),
          error.value ? h('p', { role: 'alert', class: 'text-danger' }, error.value) : null,
          loading.value ? h('p', { role: 'status', class: 'text-center py-4' }, '正在加载合同…') :
          h('div', { class: 'table-responsive' }, [h('table', { class: 'table table-hover align-middle' }, [
            h('thead', { class: 'table-light' }, [h('tr', {}, ['选择', '合同编号', '客户名称', '项目名称', '项目部门（检测部门）'].map(t => h('th', {}, t)))]),
            h('tbody', {}, rows.value.map(row => h('tr', { key: row.id, class: pending.value?.id === row.id ? 'table-active' : '',
              onClick: () => { pending.value = row } }, [
              h('td', {}, [h('input', { type: 'radio', name: 'contract-selection', class: 'form-check-input',
                'aria-label': row.agreementNo, checked: pending.value?.id === row.id, onChange: () => { pending.value = row } })]),
              ...[row.agreementNo, row.client, row.projectName, row.department]
                .map(text => h('td', { class: 'text-break' }, text || '—')),
            ]))),
          ])]),
          !loading.value && !error.value && !rows.value.length ? h('p', { class: 'text-center text-muted py-4' }, '暂无符合条件的已登记合同') : null,
          h('div', { class: 'd-flex justify-content-end align-items-center gap-2 mt-3' }, [
            button('上一页', () => { page.value--; search.cancel(); void load() }, loading.value || page.value <= 1),
            h('span', {}, `${page.value} / ${pages.value}`),
            button('下一页', () => { page.value++; search.cancel(); void load() }, loading.value || page.value >= pages.value),
          ]),
        ],
        footer: () => [button('取消', close), button('确认选择', confirm, props.disabled || !pending.value || loading.value || !!error.value, true)],
      }),
    ])
  },
})
