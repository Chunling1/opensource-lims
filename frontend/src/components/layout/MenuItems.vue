<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { flattenNavigation, type NavigationItem } from '../../router/navigation/navigation'
import MenuCollapse from './MenuCollapse.vue'
import { pageAvailability, preventUnavailableNavigation } from '../../services/platform/availability'

const props = defineProps<{ items: NavigationItem[] }>()
const route = useRoute()
const expanded = ref('')
const isActive = (to: string) => route.path === to || route.path.startsWith(`${to}/`)
const containsActive = (item: NavigationItem) => flattenNavigation([item]).some(child => isActive(child.to))
const collapseId = (item: NavigationItem) => `submenu-${item.to.replace(/^\//, '').replaceAll('/', '-')}`

watch(
  () => route.path,
  () => { expanded.value = props.items.find(item => item.children && containsActive(item))?.to || '' },
  { immediate: true },
)
</script>

<template>
  <ul class="dropdown-menu show">
    <li v-for="item in items" :key="item.to">
      <template v-if="item.children">
        <a
          class="dropdown-item dropdown-toggle"
          :href="`#${collapseId(item)}`"
          data-bs-toggle="collapse"
          role="button"
          :aria-label="item.label"
          :class="{ active: containsActive(item) }"
          :aria-expanded="expanded === item.to"
          :aria-controls="collapseId(item)"
          @click.stop.prevent="expanded = expanded === item.to ? '' : item.to"
          @keydown.space.prevent="expanded = expanded === item.to ? '' : item.to"
        >
          {{ item.label }}
        </a>
        <MenuCollapse :id="collapseId(item)" :open="expanded === item.to">
          <MenuItems :items="item.children" />
        </MenuCollapse>
      </template>
      <RouterLink
        v-else
        class="dropdown-item"
        :class="{ active: isActive(item.to) }"
        :to="item.to"
        :aria-disabled="pageAvailability(item.to).status !== 'available' || undefined"
        :title="pageAvailability(item.to).reason || undefined"
        @click.capture="preventUnavailableNavigation($event, item.to)"
        @keydown.enter.capture="preventUnavailableNavigation($event, item.to)"
      >
        {{ item.label }}{{ pageAvailability(item.to).status === 'removed' ? '（已取消）' : pageAvailability(item.to).status === 'pending' ? '（待接入）' : '' }}
      </RouterLink>
    </li>
  </ul>
</template>
