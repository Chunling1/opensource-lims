<script setup lang="ts">
import {computed,ref,watch,nextTick,onMounted,onBeforeUnmount} from 'vue'
import Dropdown from 'bootstrap/js/dist/dropdown'
import type { Modifier } from '@popperjs/core'
type Option={value:any;label:string;disabled?:boolean}
const props=defineProps<{id:string;label:string;rawValue:any;choiceOptions:Option[];placeholder?:string;readonly?:boolean;loading?:boolean;maxlength?:number;multiple?:boolean;required?:boolean;clearable?:boolean;allowCreate?:boolean;escapeOverflow?:boolean}>()
const emit=defineEmits<{'update:rawValue':[any];search:[string];clear:[]}>()
const input=ref<HTMLInputElement>(),button=ref<HTMLButtonElement>(),inputText=ref(''),query=ref('')
let dropdown:Dropdown|undefined
const selected=computed(()=>props.choiceOptions.filter(o=>props.multiple?Array.isArray(props.rawValue)&&props.rawValue.includes(o.value):props.rawValue===o.value))
const modelValue=computed(()=>selected.value[0])
const options=computed(()=>{
 const rows=props.choiceOptions.filter(o=>!query.value||o.label.toLowerCase().includes(query.value.toLowerCase()))
 if(props.allowCreate&&query.value&&!props.choiceOptions.some(o=>o.label===query.value))rows.push({value:query.value,label:query.value})
 return props.clearable&&!props.multiple?[{value:'',label:props.placeholder||'全部'},...rows.filter(o=>o.value!=='')]:rows
})
function restoreText(){inputText.value=selected.value.map(o=>o.label).join('；')||(props.rawValue==null||props.rawValue===''?'':String(props.rawValue))}
function search(value:string){if(props.readonly||props.loading)return;query.value=value;inputText.value=value;emit('search',value);void nextTick(()=>dropdown?.show())}
async function select(option:Option){
 if(props.readonly||props.loading||option.disabled)return
 const next=props.multiple?(Array.isArray(props.rawValue)&&props.rawValue.includes(option.value)?props.rawValue.filter(v=>v!==option.value):[...(Array.isArray(props.rawValue)?props.rawValue:[]),option.value]):option.value
 emit('update:rawValue',next);if(next==='')emit('clear');query.value=''
 await nextTick();restoreText();if(!props.multiple)dropdown?.hide();input.value?.focus()
}
watch(()=>[props.rawValue,props.choiceOptions],restoreText,{immediate:true,deep:true})
watch(()=>props.readonly||props.loading,disabled=>{if(disabled)dropdown?.hide()})
// A fixed menu escapes the table overflow without adding height or a vertical scrollbar.
const menuWidth: Modifier<'menuWidth', Record<string, never>> = {
 name:'menuWidth',enabled:true,phase:'beforeWrite',requires:['computeStyles'],
 fn:({state})=>{state.styles.popper.width=`${Math.min(Math.max(state.rects.reference.width,360),document.documentElement.clientWidth-32)}px`},
}
onMounted(()=>{dropdown=new Dropdown(button.value!,{
 autoClose:props.multiple?'outside':true,
 ...(props.escapeOverflow?{reference:button.value!.parentElement!,popperConfig:config=>({...config,strategy:'fixed',modifiers:[...(config.modifiers||[]),menuWidth,{name:'preventOverflow',options:{boundary:'viewport',padding:16}},{name:'flip',options:{padding:16}}]})}:{}),
})})
function resetQuery(){query.value='';restoreText()}
onBeforeUnmount(()=>{dropdown?.dispose()})
</script>
<template>
  <div class="input-group">
    <input :id="id" ref="input" class="form-control" :class="{ 'bg-body-tertiary': readonly }" :aria-label="label" :value="inputText" :placeholder="placeholder" :readonly="readonly" :required="required" :maxlength="maxlength" @input="search(($event.target as HTMLInputElement).value)" @blur="restoreText" @keydown.down.prevent="dropdown?.show()" @keydown.esc="dropdown?.hide()" />
    <button ref="button" class="btn btn-light dropdown-toggle" type="button" data-bs-toggle="dropdown" @click="resetQuery" :aria-label="loading ? `正在加载${label}选项` : `选择${label}`" :aria-busy="loading" :aria-controls="`${id}-options`" aria-expanded="false" :disabled="readonly || loading || !options.length"><span v-if="loading" class="spinner-border spinner-border-sm" aria-hidden="true"></span></button>
    <ul :id="`${id}-options`" class="dropdown-menu dropdown-menu-end" :class="{ 'w-100': !escapeOverflow }" :aria-label="`${label}选项`">
      <li v-for="option in options" :key="String(option.value)">
        <label v-if="multiple" class="dropdown-item d-flex align-items-center gap-2 text-wrap mb-0"><input class="form-check-input m-0 flex-shrink-0" type="checkbox" :checked="selected.includes(option)" :disabled="readonly || option.disabled" @change="select(option)" /><span>{{ option.label }}</span></label>
        <button v-else class="dropdown-item text-wrap" :class="{ active: modelValue === option }" type="button" :disabled="readonly || option.disabled" @click="select(option)">{{ option.label }}</button>
      </li>
    </ul>
  </div>
</template>
