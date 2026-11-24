import { computed, defineComponent, h, ref, watch, type PropType } from 'vue'
import { ElDialog } from '../controls'

type Option = { entrustNo: string; client?: string; projectName?: string; sampleCount?: number }

// A presentation adapter: it only selects an existing option and emits the original events.
export default defineComponent({
  name: 'EntrustSelection',
  props: { modelValue: String, disabled: Boolean, options: { type: Array as PropType<Option[]>, default: () => [] } },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    const open = ref(false), search = ref(''), pending = ref(''), page = ref(1)
    const selected = computed(() => props.options.find(o => o.entrustNo === props.modelValue))
    const filtered = computed(() => props.options.filter(o => [o.entrustNo, o.client, o.projectName].join(' ').toLowerCase().includes(search.value.trim().toLowerCase())))
    const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / 10)))
    watch(search, () => { page.value = 1 })
    const label = (o?: Option) => o ? `${o.entrustNo} · ${o.client || ''} · ${o.projectName || ''}` : props.modelValue || ''
    const launch = () => { if (props.disabled) return; pending.value = props.modelValue || ''; search.value = ''; page.value = 1; open.value = true }
    const confirm = () => {
      if (props.disabled || !props.options.some(o => o.entrustNo === pending.value)) return
      if (pending.value !== props.modelValue) { emit('update:modelValue', pending.value); emit('change', pending.value) }
      open.value = false
    }
    const button = (text: string, onClick: () => void, disabled = false, primary = false) => h('button', { type: 'button', class: `btn btn-${primary ? 'primary' : 'light'}`, disabled, onClick }, text)
    return () => h('div', { class: 'w-100' }, [
      h('div', { class: 'input-group' }, [h('input', { class: 'form-control', readonly: true, disabled: props.disabled, value: label(selected.value), placeholder: '请选择委托单', 'aria-label': '已关联委托单', onClick: launch }), button('选择委托单', launch, props.disabled)]),
      h(ElDialog, { modelValue: open.value, 'onUpdate:modelValue': (v: boolean) => { open.value = v }, title: '选择委托单', width: '1100px', closeOnClickModal: false }, {
        default: () => [
          h('input', { class: 'form-control mb-3', placeholder: '搜索委托编号、委托单位或工程名称', value: search.value, onInput: (e: Event) => { search.value = (e.target as HTMLInputElement).value } }),
          h('div', { class: 'd-flex flex-wrap align-items-center gap-2 mb-3' }, [h('span', { class: 'text-muted' }, `共 ${filtered.value.length} 条`), pending.value ? h('span', { class: 'badge bg-primary-transparent text-wrap text-start' }, `已选：${label(props.options.find(o => o.entrustNo === pending.value))}`) : null]),
          h('div', { class: 'table-responsive' }, [h('table', { class: 'table table-hover align-middle' }, [
            h('thead', { class: 'table-light' }, [h('tr', {}, ['选择', '委托编号', '委托单位', '工程名称', '已有样品'].map(t => h('th', {}, t)))]),
            h('tbody', {}, filtered.value.slice((page.value - 1) * 10, page.value * 10).map(o => h('tr', { key: o.entrustNo, class: pending.value === o.entrustNo ? 'table-active' : '', onClick: () => { pending.value = o.entrustNo } }, [
              h('td', {}, [h('input', { type: 'radio', class: 'form-check-input', name: 'entrust-selection', 'aria-label': o.entrustNo, checked: pending.value === o.entrustNo, onChange: () => { pending.value = o.entrustNo } })]),
              ...[o.entrustNo, o.client || '—', o.projectName || '—', String(o.sampleCount ?? 0)].map(text => h('td', { class: 'text-break' }, text)),
            ]))),
          ])]),
          !filtered.value.length ? h('p', { class: 'text-center text-muted py-4' }, '暂无符合条件的委托单') : null,
          h('div', { class: 'd-flex align-items-center justify-content-end gap-2 mt-3' }, [button('上一页', () => { page.value-- }, page.value <= 1), h('span', {}, `${page.value} / ${pages.value}`), button('下一页', () => { page.value++ }, page.value >= pages.value)]),
        ],
        footer: () => [button('取消', () => { open.value = false }), button('确认选择', confirm, props.disabled || !pending.value, true)],
      }),
    ])
  },
})
