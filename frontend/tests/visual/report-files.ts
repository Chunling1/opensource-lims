// Local component fixture. All API requests are intercepted; no production data.
import {createApp, h} from 'vue'
import * as controls from '../../src/platformUi/controls'
import Panel from '../../src/modules/components/ReportArtifactPanel.vue'
const nativeFetch=window.fetch.bind(window)
window.fetch=async (input,init)=>{
 const url=String(input)
 if(!url.includes('/api/'))return nativeFetch(input,init)
 const denied=url.includes('QA-DENIED')&&url.includes('signed=1')
 return new Response(JSON.stringify({code:denied?403:0,message:denied?'报告签发下载签字盖章版需要盖章报告下载权限':'ok',data:denied?null:{kind:url.includes('signed=1')?'signed':'controlled',canPreview:!url.includes('signed=1'),canDownload:true}}),{status:denied?403:200,headers:{'content-type':'application/json'}})
}
const app=createApp({render:()=>h('main',{class:'container py-4'},[
 h('h1',{class:'h4 mb-4'},'报告文件 · 本地隔离验收'),
 h('nav',{class:'mb-4'},'报告签发 / 我的签署 / 报告归档 / 报告发放 / 报告查询'),
 ...[['报告查询 · 有下载权限','query','QA-001'],['报告签发 · 无下载权限','print','QA-DENIED'],['报告归档 · 仅未签章原件','archive','QA-003']].flatMap(([title,view,reportNo])=>[h('h2',{class:'h6 mt-4'},title),h(Panel,{view,reportNo})])
])})
for(const [name,component] of Object.entries(controls))if(name.startsWith('El'))app.component(name,component as any)
app.mount('#app')
