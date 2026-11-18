<script setup lang="ts">
// 顶栏右侧：站内提醒 + 用户菜单（Tabler 官方 dropdown 结构，由 tabler.esm 的 data-API 驱动）
import { IconBell, IconLogout } from '@tabler/icons-vue'
import type { User } from './api'
defineProps<{ user: User; notices: { number: string; message: string }[]; dark?: boolean }>()
const emit = defineEmits<{ refresh: []; logout: [] }>()
</script>
<template>
  <div class="navbar-nav flex-row order-md-last align-items-center gap-1">
    <div class="nav-item dropdown">
      <a
        href="#"
        class="nav-link px-0 me-2"
        data-bs-toggle="dropdown"
        data-bs-auto-close="outside"
        role="button"
        aria-label="站内提醒"
        @click.prevent="emit('refresh')"
      >
        <IconBell class="icon" />
        <span v-if="notices.length" class="badge bg-red text-red-fg badge-notification badge-pill">{{
          notices.length
        }}</span>
      </a>
      <div class="dropdown-menu dropdown-menu-arrow dropdown-menu-end dropdown-menu-card">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title h4">站内提醒</h3>
          </div>
          <div class="list-group list-group-flush list-group-hoverable">
            <div v-for="n in notices" :key="n.number" class="list-group-item">
              <div class="row align-items-center">
                <div class="col-auto"><span class="status-dot status-dot-animated bg-red d-block"></span></div>
                <div class="col text-truncate">
                  <div class="text-body">{{ n.number }}</div>
                  <div class="d-block text-secondary text-truncate mt-n1">{{ n.message }}</div>
                </div>
              </div>
            </div>
            <div v-if="!notices.length" class="list-group-item text-secondary">当前没有站内消息。</div>
          </div>
        </div>
      </div>
    </div>
    <div class="nav-item dropdown">
      <a
        href="#"
        class="nav-link d-flex lh-1 p-0 px-2"
        data-bs-toggle="dropdown"
        role="button"
        aria-label="用户菜单"
        @click.prevent
      >
        <span class="avatar avatar-sm" :class="dark ? 'bg-white text-primary' : 'bg-primary-lt'">{{
          user.name.slice(-1)
        }}</span>
        <div class="d-none d-xl-block ps-2 text-start">
          <div>{{ user.name }}</div>
          <div class="mt-1 small text-secondary">{{ user.department }}</div>
        </div>
      </a>
      <div class="dropdown-menu dropdown-menu-end dropdown-menu-arrow">
        <span class="dropdown-header">{{ user.department }} · {{ user.name }}</span>
        <div class="dropdown-divider"></div>
        <button type="button" class="dropdown-item" @click="emit('logout')">
          <IconLogout class="icon dropdown-item-icon" />退出
        </button>
      </div>
    </div>
  </div>
</template>
