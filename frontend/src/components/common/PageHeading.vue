<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { navigation, flattenNavigation } from '../../router/navigation/navigation'

const props = defineProps<{ title: string; parentTo?: string }>()
const route = useRoute()
const ancestors = computed(() => {
  const matches = navigation.flatMap(group => flattenNavigation(group.children, true)
    .filter(item => route.path === item.to || route.path.startsWith(`${item.to}/`))
    .map(item => ({ group, item })))
    .sort((a, b) => a.item.to.length - b.item.to.length)
  const group = matches.at(-1)?.group
  if (!group) return []
  return [
    { label: group.label, to: undefined as string | undefined },
    ...matches.filter(match => match.group === group && match.item.to !== route.path)
      .map(({ item }) => ({ label: item.label, to: item.children ? undefined : props.parentTo?.split('?')[0] === item.to && !/[\\\r\n#]/.test(props.parentTo) ? props.parentTo : item.to })),
  ]
})
</script>
<template>
  <div class="row"><div class="col-12"><div class="page-title-box d-sm-flex align-items-center justify-content-between bg-galaxy-transparent">
    <h4 class="mb-sm-0">{{ title }}</h4>
    <nav class="page-title-right" aria-label="面包屑"><ol class="breadcrumb m-0"><li v-for="(item, index) in ancestors" :key="index" class="breadcrumb-item"><RouterLink v-if="item.to" :to="item.to">{{ item.label }}</RouterLink><span v-else>{{ item.label }}</span></li><li class="breadcrumb-item active" aria-current="page">{{ title }}</li></ol></nav>
  </div></div></div>
</template>
