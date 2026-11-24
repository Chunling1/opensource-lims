<script setup lang="ts">
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import NotificationMessages from '../../components/common/NotificationMessages.vue'
import LoadState from '../../components/common/LoadState.vue'
import { currentActor, roleLabels, switchIdentity, identities } from '../../stores/session'
import { subscribeDatabase } from '../../services/storage/database'

const route = useRoute(), mode = computed(() => String(route.meta.operation)), title = computed(() => String(route.meta.title))
const ready = ref(false), loading = ref(false), loadError = ref<ErrorValue>('')
const error = ref<ErrorValue>(''), success = ref('')
const actors = ref<{ id: string; name: string }[]>([])
let sequence = 0, loadedKey = ''

async function load() {
  const token = ++sequence, key = `${mode.value}:${JSON.stringify(currentActor.value)}`
  if (key !== loadedKey) { loadedKey = key; ready.value = false; actors.value = []; error.value = ''; success.value = '' }
  const currentMode = mode.value
  loading.value = !ready.value; loadError.value = ''
  try {
    const result = currentMode === 'identity' ? await identities() : []
    if (token !== sequence) return
    actors.value = result
    ready.value = true
  } catch (e) {
    if (token === sequence) {
      loadError.value = normalizeError(e)
      if (['FORBIDDEN', 'UNAUTHORIZED'].includes(loadError.value.code)) { ready.value = false; actors.value = [] }
    }
  } finally { if (token === sequence) loading.value = false }
}

watch([mode, currentActor], load, { immediate: true })
const unsub = subscribeDatabase(() => { if (mode.value === 'identity') load() })
onBeforeUnmount(() => { unsub(); sequence++ })
async function identity(id: string) { error.value = ''; success.value = ''; try { await switchIdentity(id); success.value = '演示身份已切换。' } catch (e) { error.value = normalizeError(e) } }
</script>
<template>
  <PageHeading :title="title" />
  <TemplateToast :message="success" tone="success" auto-show /><LoadState :loading="loading" :error="loadError" :has-data="ready" @retry="load" /><ErrorNotice :error="error" />
  <template v-if="ready">
    <section v-if="mode === 'notifications'" aria-label="演示通知"><NotificationMessages /></section>
    <div v-if="mode === 'identity'" class="card"><div class="card-header"><h5 class="card-title mb-0">演示身份</h5></div><div class="card-body"><div class="alert alert-info">当前为浏览器本地模拟登录。不同身份用于验证岗位分工与审批流程。</div><p>当前：<strong>{{ currentActor.name }}</strong> · {{ currentActor.roles.map(role => roleLabels[role] || role).join(' / ') }}</p><div class="row g-3"><div v-for="person in actors" :key="person.id" class="col-md-4"><button class="btn w-100" :class="person.id === currentActor.id ? 'btn-primary' : 'btn-primary-lt'" @click="identity(person.id)">{{ person.name }}</button></div></div></div></div>
  </template>
</template>

