<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { navigation as allNavigation, navigationSections, flattenNavigation, filterNavigation } from '../../router/navigation/navigation'
import { currentActor } from '../../stores/session'
import { useThemeStore } from '../../stores/theme/index'
import UserMenu from './UserMenu.vue'
import TemplateScroll from '../common/TemplateScroll.vue'
import MenuCollapse from './MenuCollapse.vue'
import MenuItems from './MenuItems.vue'
import BrandLogo from './BrandLogo.vue'
import { allowedWorkbench } from '../../types/dashboard'
import { correctionPage } from '../../services/platform/correctionAccess'
import { profile } from '../../services/platform/auth'

const menuScroll = ref<InstanceType<typeof TemplateScroll>>()
defineEmits<{ settings: [] }>()
const theme = useThemeStore()
const route = useRoute()

const navigation = computed(() =>
  allNavigation
    .map(g => ({
      ...g,
      children: filterNavigation(g.children, i =>
        correctionPage(i.to)
          ? true
          : i.to === '/inspection/quality/erp_content'
            ? !!profile.value?.features?.businessDataCorrection
            : i.workbench
              ? allowedWorkbench(currentActor.value, i.workbench)
              : i.permission
                ? !!profile.value?.permissions.includes(i.permission)
                : i.to === '/reports/check'
                  ? !!profile.value?.permissions.includes('report.view')
                  : true,
      ),
    }))
    .filter(g => g.children.length),
)

const activeGroup = computed(
  () =>
    navigation.value.find(g => flattenNavigation(g.children).some(i => route.path === i.to || route.path.startsWith(i.to + '/')))?.id ||
    (route.path.startsWith('/samples') ? 'samples' : 'overview'),
)
const expanded = ref(activeGroup.value)

watch(
  () => route.path,
  async () => {
    expanded.value = activeGroup.value
    theme.mobileOpen = false
    await nextTick()
    menuScroll.value?.reveal(document.querySelector('#sidebar-menu a.active'))
  },
)

function toggle(group: string) {
  if (theme.collapsed && theme.viewport >= 992) {
    theme.collapsed = false
    expanded.value = group
    return
  }
  expanded.value = expanded.value === group ? '' : group
}
</script>

<template>
  <aside class="navbar navbar-vertical navbar-expand-lg" :data-bs-theme="theme.settings.sidebar" aria-label="主导航">
    <div class="container-fluid">
      <button
        class="navbar-toggler"
        type="button"
        aria-controls="sidebar-menu"
        :aria-expanded="theme.mobileOpen"
        aria-label="切换导航菜单"
        @click="theme.mobileOpen = !theme.mobileOpen"
      >
        <span class="navbar-toggler-icon"></span>
      </button>

      <div class="navbar-brand navbar-brand-autodark d-flex align-items-center justify-content-between w-100 px-2">
        <BrandLogo :compact="theme.collapsed && theme.viewport >= 992" sidebar />
        <button
          type="button"
          class="btn btn-sm btn-ghost-secondary d-none d-lg-inline-flex p-1"
          aria-label="折叠或展开侧栏"
          :aria-pressed="theme.collapsed"
          @click="theme.toggleMenu()"
        >
          <i aria-hidden="true" class="ti" :class="theme.collapsed ? 'ti-layout-sidebar-left-expand' : 'ti-layout-sidebar-left-collapse'"></i>
        </button>
      </div>

      <UserMenu v-if="theme.settings.user === 'show'" sidebar @settings="$emit('settings')" />

      <div id="sidebar-menu" class="collapse navbar-collapse" :class="{ show: theme.mobileOpen }">
        <TemplateScroll ref="menuScroll" class="w-100 flex-grow-1" label="主导航菜单">
          <ul id="navbar-nav" class="navbar-nav pt-lg-2">
            <template v-for="(group, index) in navigation" :key="group.id">
              <li v-if="index === 0 || navigation[index - 1]?.section !== group.section" class="lims-sidebar-section">
                <span>{{ navigationSections[group.section] }}</span>
              </li>
              <li class="nav-item dropdown">
                <a
                  class="nav-link dropdown-toggle"
                  :class="{ active: activeGroup === group.id, show: expanded === group.id }"
                  :href="`#menu-${group.id}`"
                  data-bs-toggle="collapse"
                  role="button"
                  :aria-label="group.label"
                  :aria-expanded="expanded === group.id"
                  :aria-controls="`menu-${group.id}`"
                  @click.stop.prevent="toggle(group.id)"
                >
                  <span class="nav-link-icon d-md-none d-lg-inline-block">
                    <i aria-hidden="true" :class="group.icon"></i>
                  </span>
                  <span class="nav-link-title">{{ group.label }}</span>
                </a>
                <MenuCollapse :id="`menu-${group.id}`" :open="expanded === group.id">
                  <MenuItems :items="group.children" />
                </MenuCollapse>
              </li>
            </template>
          </ul>
        </TemplateScroll>
      </div>
    </div>
  </aside>
</template>
