<template><el-button size="small" @click="open">外部ERP回传 / 反审核</el-button></template>
<script setup lang="ts">
// The management endpoint independently authenticates and authorizes each action.
function open(){ window.location.assign('/api/erp-outbound/console') }
</script>
