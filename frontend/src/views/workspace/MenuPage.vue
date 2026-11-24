<script setup lang="ts">
import { useRoute } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
const route = useRoute()
</script>
<template><PageHeading :title="String(route.meta.title)" /></template>
