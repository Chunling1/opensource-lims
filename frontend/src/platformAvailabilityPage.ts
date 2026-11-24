import { computed, defineComponent, h } from 'vue'
import { useRoute } from 'vue-router'
import ErrorPage from './components/common/ErrorPage.vue'
import { AppError } from './services/common/errors'
import { pageAvailability } from './services/platform/availability'

// Reuse the package's complete error-page component, without new markup or CSS.
export const PlatformAvailabilityPage = defineComponent({
  setup() {
    const route = useRoute()
    const state = computed(() => pageAvailability(String(route.query.destination || '')))
    const error = computed(() => new AppError('BUSINESS_RULE', state.value.reason || '该入口当前不可用。', { status: 0 }))
    return () => h(ErrorPage, { error: error.value, title: state.value.status === 'removed' ? '现平台不适用' : '待接入', backTo: '/dashboard', backLabel: '返回工作台', retry: false })
  },
})
