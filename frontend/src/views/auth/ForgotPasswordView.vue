<script setup lang="ts">
import { useRoute } from 'vue-router'
import AuthLayout from '../../components/auth/AuthLayout.vue'
import { loginReturn } from '../../router/modules/auth'
const route = useRoute()
</script>
<template>
  <AuthLayout title="忘记密码"><div class="text-center"><i class="ti ti-lock-password display-4 text-primary" aria-hidden="true"></i><p class="my-4">请联系管理员重置密码。</p><RouterLink :to="{ path: '/login', query: { redirect: loginReturn(route.query.redirect) } }" class="btn btn-success w-100">返回登录</RouterLink></div></AuthLayout>
</template>
