<script setup lang="ts">
import RegistrationContractPicker from '../commissions/RegistrationContractPicker.vue'
import { clientYearRange } from '../../services/common/date'
import type { RegistrationContract } from '../../types/commissions/commissionForm'
defineProps<{ linked: string[] }>()
const emit = defineEmits<{ close: []; select: [RegistrationContract[]] }>()
const initialDates = clientYearRange()
</script>
<template>
  <RegistrationContractPicker open multiple :linked="linked" :initial-dates="initialDates" @close="emit('close')" @select-many="emit('select', $event)" />
</template>
