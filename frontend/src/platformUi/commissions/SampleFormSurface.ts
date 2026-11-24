import { defineComponent, h, nextTick, watch, type PropType } from 'vue'

// Presentation only. Closing always goes through the existing wizard draft guard.
export default defineComponent({
  name: 'SampleFormSurface', inheritAttrs: false,
  props: {
    modelValue: Boolean,
    embedded: Boolean,
    returnLabel: { type: String, default: '返回样品登记' },
    formLabel: { type: String, default: '样品信息表单' },
    beforeClose: Function as PropType<(done: () => void) => void>,
  },
  emits: ['update:modelValue', 'close', 'closed', 'open', 'opened'],
  setup(props, { slots, emit }) {
    const close = () => {
      const done = () => { emit('update:modelValue', false); emit('close'); emit('closed') }
      props.beforeClose ? props.beforeClose(done) : done()
    }
    watch(() => props.modelValue, async open => {
      if (open && !props.embedded) { emit('open'); await nextTick(); window.scrollTo({ top: 0 }); emit('opened') }
    })
    return () => props.modelValue ? h('section', { 'aria-label': props.formLabel }, [
      !props.embedded && h('div', { class: 'd-flex flex-wrap align-items-center justify-content-between gap-2 mb-3' }, [
        h('button', { type: 'button', class: 'btn btn-light', onClick: close }, [
          h('i', { class: 'ti ti-arrow-left me-1', 'aria-hidden': 'true' }), props.returnLabel,
        ]),
        h('div', { class: 'fw-semibold' }, slots.header?.()),
      ]),
      slots.default?.(),
      !props.embedded && h('div', { class: 'card mb-0' }, [h('div', { class: 'card-body d-flex flex-wrap justify-content-end gap-2' }, slots.footer?.())]),
    ]) : null
  },
})
