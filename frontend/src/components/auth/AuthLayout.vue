<script setup lang="ts">
import { ref, useId } from 'vue'
defineProps<{ title: string }>()
const messages = ['开源实验室信息管理系统', '委托、样品、检测与报告全流程管理', '让每一份样品都有迹可循']
const activeMessage = ref(0)
const carouselId = useId()
</script>

<template>
  <div class="page page-center min-vh-100 py-5">
    <div class="container container-lg my-auto">
      <div class="card card-md overflow-hidden shadow-sm">
        <div class="row g-0">
          <div class="col-lg-6 bg-primary text-white p-4 p-lg-5 d-flex flex-column justify-content-between">
            <div class="d-flex align-items-center gap-2 mb-4">
              <span class="avatar bg-white text-primary rounded">
                <i class="ti ti-flask fs-2" aria-hidden="true"></i>
              </span>
              <span class="fs-2 fw-bold">LIMS</span>
            </div>
            <div class="my-auto py-4">
              <div class="mb-3"><i class="ti ti-quote fs-1 opacity-75" aria-hidden="true"></i></div>
              <div :id="carouselId" class="carousel slide" role="region" aria-label="LIMS 系统介绍">
                <div class="carousel-indicators">
                  <button v-for="(message, index) in messages" :key="message" type="button" :data-bs-target="`#${carouselId}`" :class="{ active: activeMessage === index }" :aria-current="activeMessage === index ? 'true' : undefined" :aria-label="`系统介绍 ${index + 1}`" @click="activeMessage = index"></button>
                </div>
                <div class="carousel-inner text-center text-white pb-5">
                  <div v-for="(message, index) in messages" :key="message" class="carousel-item" :class="{ active: activeMessage === index }">
                    <p class="fs-4 fw-medium mb-0">{{ message }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div class="small opacity-75">Laboratory Information Management System</div>
          </div>
          <div class="col-lg-6">
            <div class="card-body p-4 p-lg-5">
              <h1 class="h2 mb-1">{{ title }}</h1>
              <p class="text-secondary mb-4">欢迎使用 LIMS 实验室信息管理系统</p>
              <slot />
              <div v-if="$slots.links" class="text-center mt-4"><slot name="links" /></div>
            </div>
          </div>
        </div>
      </div>
      <div class="text-center text-secondary mt-3">© {{ new Date().getFullYear() }} LIMS</div>
    </div>
  </div>
</template>
