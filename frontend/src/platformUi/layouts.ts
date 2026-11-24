import { Comment, Text, Fragment, cloneVNode, defineComponent, h, isVNode, useId, type VNode } from 'vue'
import AdaptiveTableActions from '../components/common/table/AdaptiveTableActions.vue'

// Business slots retain their event/model contracts. Their layout is owned here
// by the supplied template's grid and toolbar, never by the legacy page CSS.
export function visibleNodes(nodes: unknown[]): VNode[] {
  return nodes.flatMap(node => !isVNode(node) || node.type === Comment || node.type === Text && !String(node.children || '').trim() ? []
    : node.type === Fragment ? visibleNodes(node.children as unknown[] || []) : [node])
}
function fields(nodes: unknown[]): VNode[] {
  return visibleNodes(nodes).flatMap(node => node.type === 'div' && Array.isArray(node.children)
    && !node.props?.role && !node.props?.onClick
    ? fields(node.children) : [node])
}
export const TemplateFilterFields = defineComponent({
  setup(_, { slots }) {
    const prefix = useId()
    return () => h('div', { class: 'row g-3 align-items-end' }, fields(slots.default?.() || []).map((node, index) => {
      const props = node.props || {}, id = props.id || `${prefix}-filter-${index}`
      const placeholder = String(props['aria-label'] || props.label || props.placeholder || '')
      const rangeStart = props.startPlaceholder || props['start-placeholder']
      const range = props.mode === 'range' || rangeStart
      const label = props['data-filter-label'] || (range ? String(rangeStart || '日期范围').replace('开始', '').replace('起始', '') : placeholder || '筛选条件')
      const controlName = typeof node.type === 'string' ? node.type : (node.type as {name?:string;__name?:string}).name || (node.type as {__name?:string}).__name || ''
      const action = /button/i.test(controlName) || node.type === 'button'
      return h('div', { class: 'col-12 col-sm-6 col-xl-4', key: node.key ?? index }, [
        !action ? h('label', { class: 'form-label', for: id }, label) : null,
        cloneVNode(node, { id, 'aria-label': label }),
      ])
    }))
  },
})

const iconFor = (label: string) => /新增|添加|新建/.test(label) ? 'ti ti-plus'
  : /删除/.test(label) ? 'ti ti-trash' : /导出|下载/.test(label) ? 'ti ti-download'
  : /导入|上传/.test(label) ? 'ti ti-upload' : /修改|编辑|修订/.test(label) ? 'ti ti-edit'
  : /查看|预览/.test(label) ? 'ti ti-eye' : /撤销|退回/.test(label) ? 'ti ti-arrow-back-up' : 'ti ti-dots'
function nodeText(nodes: unknown): string {
  return (Array.isArray(nodes) ? nodes : [nodes]).map(node => typeof node === 'string' ? node : isVNode(node)
    ? typeof node.children === 'string' ? node.children : Array.isArray(node.children) ? nodeText(node.children) : '' : '').join('').trim()
}
export const TemplateBusinessActions = defineComponent({
  props: { label: { type: String, default: '业务' } },
  setup(props, { slots }) {
    return () => {
      const nodes = visibleNodes(slots.default?.() || [])
      const controls = nodes.filter(n => typeof n.props?.onClick === 'function')
      const extra = nodes.filter(n => !controls.includes(n))
      const entries = controls.map(node => {
        const children = node.children as {default?:()=>VNode[]} | undefined
        const label = nodeText(typeof node.children === 'string' ? [node.children] : children?.default?.() || [])
        return { label, icon: iconFor(label), disabled: node.props?.disabled === '' || !!node.props?.disabled || !!node.props?.loading,
          busy: !!node.props?.loading, hint: node.props?.title, ariaLabel: node.props?.['aria-label'] }
      })
      const primaryIndex = entries.findIndex(entry => /^(新增|添加|新建)/.test(entry.label))
      const primary = primaryIndex >= 0 ? h('button', {type:'button',class:'btn btn-primary text-nowrap',disabled:entries[primaryIndex]?.disabled,onClick:(event:MouseEvent)=>controls[primaryIndex]?.props?.onClick(event)},[h('i',{class:'ti ti-plus me-1','aria-hidden':true}),entries[primaryIndex]?.label]) : undefined
      const secondary = entries.map((entry,index)=>({entry,index})).filter(item=>item.index!==primaryIndex)
      return h(AdaptiveTableActions, { label: props.label, actions: secondary.map(item=>item.entry), tableControls: false,
        onAction: (index: number) => { const original = secondary[index]?.index; if (original !== undefined && !entries[original]?.disabled) controls[original]?.props?.onClick(new MouseEvent('click')) },
      }, primary || extra.length ? {default:()=>[primary,...extra]} : undefined)
    }
  },
})
