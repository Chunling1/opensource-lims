// @ts-nocheck
import { ref, onMounted, defineComponent, createElementVNode as el, createVNode as vnode } from 'vue'
import { request } from './http'
import { useSessionStore } from '@/stores/session'
import { ElMessage } from 'element-plus'

export const strongPassword = value => value.length >= 8 && value.length <= 128 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /[0-9]/.test(value) && /[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/.test(value);

export function downloadInitialCredentials(result) {
  const rows=result?.initialCredentials;
  if(!Array.isArray(rows)||!rows.length)return;
  const safe=value=>'"'+String(value??'').replace(/^[=+\-@\t\r]/,"'$&").replaceAll('"','""')+'"';
  const table=[['账号','姓名','部门','初始密码','账号状态'],...rows.map(r=>[r.account,r.name,r.department,r.initialPassword,r.enabled?'启用':'停用'])];
  const url=URL.createObjectURL(new Blob(['\ufeff'+table.map(row=>row.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='新建人员初始密码.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  ElMessage.success('新建账号的初始密码表已下载，请保存并分发；首次登录必须改密');
}

export function useLoginCaptcha() {
  const image = ref(''), id = ref(''), answer = ref(''), error = ref(''), busy = ref(false);
  async function refresh() {
    if (busy.value) return;
    busy.value = true; id.value = ''; answer.value = ''; image.value = ''; error.value = '';
    try {
      const data = await request('/api/auth/captcha', {cache:'no-store',signal:AbortSignal.timeout(10000)});
      id.value = data.captchaId; image.value = data.image;
    } catch (e) { error.value = e.message || '验证码加载失败，请点击重试'; }
    finally { busy.value = false; }
  }
  function values() {
    if (!id.value || !/^\d{6}$/.test(answer.value)) throw new Error('请输入图片中的 6 位数字验证码');
    return {captchaId:id.value,captcha:answer.value};
  }
  onMounted(refresh);
  const Component = () => el('div', {class:'login-captcha',style:'margin:18px 0'}, [
    el('label', {for:'login-numeric-captcha',style:'display:block;margin-bottom:8px;font-size:14px;color:#303844'}, '图片验证码'),
    el('div', {style:'display:flex;gap:12px;align-items:center;flex-wrap:wrap'}, [
      el('input', {id:'login-numeric-captcha',value:answer.value,inputmode:'numeric',autocomplete:'off',maxlength:6,
        placeholder:'6 位数字',disabled:busy.value,'aria-label':'图片验证码',
        style:'min-width:90px;flex:1;width:100px;height:46px;padding:0 12px;border:1px solid #c7d1df;border-radius:7px;font:inherit',
        onInput:event => {answer.value=event.target.value.replace(/\D/g,'').slice(0,6)}}),
      el('button', {type:'button',onClick:refresh,disabled:busy.value,title:'点击更换验证码','aria-label':'更换验证码',
        style:'border:1px solid #d5deeb;background:#f2f6ff;padding:0;border-radius:7px;min-width:150px;height:50px;cursor:pointer'},
        image.value ? [el('img',{src:image.value,alt:'六位数字验证码',width:160,height:48,style:'display:block;object-fit:contain'})] : (busy.value?'加载中…':'点击重试'))]),
    error.value ? el('p',{role:'alert',style:'color:#a52121;font-size:13px'},error.value) : null,
  ]);
  return {Component,refresh,values};
}

const css = '.login-security-mask{position:fixed;inset:0;z-index:4000;background:#14233d66;display:grid;place-items:center;padding:20px}.login-security-panel{background:white;border-radius:12px;width:min(1080px,100%);max-height:92vh;overflow:auto;color:#27364b;box-shadow:0 18px 60px #14233d33;padding:24px;box-sizing:border-box}.login-security-panel h2{margin:0;font-size:22px}.login-security-panel h3{margin:24px 0 10px}.login-security-panel p{line-height:1.6}.login-security-panel header,.login-security-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:space-between}.login-security-actions{justify-content:flex-start;margin:14px 0}.login-security-panel button,.login-security-entry{padding:9px 15px;border-radius:7px;border:1px solid #c8d3e3;background:white;color:#27364b;cursor:pointer;font:inherit}.login-security-panel button:disabled{opacity:.5;cursor:not-allowed}.login-security-panel .primary{background:#2256dc;border-color:#2256dc;color:white}.login-security-panel .danger{background:#b72e27;border-color:#b72e27;color:white}.login-security-panel input[type=text]{padding:9px 12px;border:1px solid #c8d3e3;border-radius:7px}.login-security-panel table{border-collapse:collapse;width:100%;font-size:14px}.login-security-panel th,.login-security-panel td{padding:10px;text-align:left;border-bottom:1px solid #e4e9f0;white-space:nowrap}.login-security-panel th{background:#f3f6fb}.login-security-panel :focus-visible{outline:3px solid #91b4ff;outline-offset:3px}.login-security-panel .error{color:#a52121}.login-security-panel .status{color:#1c4e80}@media(max-width:600px){.login-security-mask{padding:8px}.login-security-panel{padding:16px}}';
const results = {success:'登录成功',first_login_required:'首次登录待改密',invalid_credentials:'账号或密码错误',locked:'锁定中',password_locked:'达到 5 次错误，已锁定',captcha_rejected:'验证码未通过',change_locked:'改密时账号锁定',change_wrong_password:'原密码错误',password_changed:'密码修改成功'};
export const SecurityAdminPanel = defineComponent({
  name:'LoginSecurityAdmin',
  setup() {
    const session=useSessionStore(), opened=ref(false), busy=ref(false), message=ref(''), error=ref('');
    const rows=ref([]), page=ref(1), total=ref(0), filter=ref(''), recordsBusy=ref(false);
    const ready=ref(false), saved=ref(false), applied=ref(false), downloaded=ref(false);
    let planId='', credentials=[];
    async function loadRecords() {
      recordsBusy.value=true; error.value='';
      try {
        const data=await request('/api/auth/security/login-records?page='+page.value+'&account='+encodeURIComponent(filter.value));
        rows.value=data.rows;total.value=data.total;
      } catch(e) {error.value=e.message || '登录记录读取失败';}
      finally {recordsBusy.value=false;}
    }
    function download() {
      if(!ready.value) return;
      const safe=value=>'"'+String(value??'').replace(/^[=+\-@\t\r]/,"'$&").replaceAll('"','""')+'"';
      const table=[['账号','姓名','部门','初始密码','账号状态','密码状态'],...credentials.map(r=>[r.account,r.name,r.department,r.initialPassword,r.enabled?'启用':'停用',applied.value?'已生效，首次登录必须改密':'待确认生效'])];
      const blob=new Blob(['\ufeff'+table.map(row=>row.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});
      const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;
      link.download='账号初始密码-'+(applied.value?'已生效':'待生效')+'-'+new Date().toISOString().slice(0,10)+'.csv';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000); downloaded.value=true;
    }
    async function prepare() {
      if(busy.value) return;
      busy.value=true;error.value='';ready.value=false;saved.value=false;applied.value=false;downloaded.value=false;credentials=[];
      try {
        const plan=await request('/api/auth/security/reset-plan',{method:'POST'});planId=plan.planId;
        let complete=false;
        while(!complete) {
          const part=await request('/api/auth/security/reset-plan/'+encodeURIComponent(planId)+'/next',{method:'POST'});
          credentials.push(...part.rows);message.value='已生成 '+part.prepared+' / '+part.total+' 个账号的初始密码';complete=part.complete;
        }
        ready.value=true;message.value+='。请下载并保存表格，30 分钟内确认生效。';download();
      } catch(e) {credentials=[];planId='';error.value=(e.message||'生成失败')+'。现有密码未修改，请重新生成。';}
      finally {busy.value=false;}
    }
    async function apply() {
      if(busy.value || !ready.value || !saved.value || !downloaded.value || applied.value) return;
      if(!window.confirm('确认重置全部账号密码？所有人员（包括当前管理员）将需要重新登录，并在首次登录时修改密码。请确认密码表已保存。')) return;
      busy.value=true;error.value='';
      try {
        const data=await request('/api/auth/security/reset-plan/'+encodeURIComponent(planId)+'/apply',{method:'POST',body:JSON.stringify({confirmation:'SAVED_PASSWORD_TABLE'})});
        applied.value=true;message.value=data.count+' 个账号的初始密码已生效。请保存已生效表格，再关闭窗口并重新登录。';download();
      } catch(e) {error.value=(e.message||'未收到重置结果')+'。如果网络中断，请先用表格中的管理员初始密码核验结果，勿重复操作。';}
      finally {busy.value=false;}
    }
    function close() {
      if(busy.value) return;
      if(ready.value&&!applied.value&&!window.confirm('关闭将丢弃本次待生效重置准备，现有密码不变。确定关闭？')) return;
      credentials=[];planId='';opened.value=false;ready.value=false;saved.value=false;
      if(applied.value) {session.clear();location.hash='/login';location.reload();}
    }
    const button=(text,onclick,disabled=false,cls='')=>el('button',{type:'button',onClick:onclick,disabled,class:cls},text);
    return () => !session.fullPlatformAuthority&&session.roleKey!=='admin'&&session.account!=='admin' ? null : el('span',{},[
      el('style',{},css),el('button',{type:'button',class:'login-security-entry',onClick:()=>{opened.value=true;loadRecords()}},'登录安全'),
      opened.value?el('div',{class:'login-security-mask'},[
        el('section',{class:'login-security-panel',role:'dialog','aria-modal':'true','aria-label':'登录安全'},[
          el('header',{},[el('h2',{},'登录安全'),button('关闭',close,busy.value)]),
          el('p',{},'密码规则：至少 8 位，包含大写英文、小写英文、数字和特殊字符。15 分钟内密码错误 5 次，锁定 30 分钟。'),
          el('h3',{},'全部人员初始密码'),
          el('p',{},'初始密码为账号加随机 5 位数字，每次重置重新生成；首次登录必须修改。先保存账号密码表，再确认生效。账号权限及启用状态保持不变。'),
          el('div',{class:'login-security-actions'},[button(busy.value?'处理中…':'生成账号密码表',prepare,busy.value||applied.value,'primary'),button('下载密码表',download,!ready.value||busy.value)]),
          ready.value&&!applied.value?el('label',{},[el('input',{type:'checkbox',checked:saved.value,disabled:busy.value,onChange:e=>saved.value=e.target.checked}),' 我已保存密码表，并确认可以重置全部账号']):null,
          ready.value&&!applied.value?el('div',{class:'login-security-actions'},[button('确认重置全部密码',apply,!saved.value||busy.value||!downloaded.value,'danger')]):null,
          message.value?el('p',{class:'status',role:'status'},message.value):null,
          error.value?el('p',{class:'error',role:'alert'},error.value):null,
          !applied.value?el('div',{},[
            el('h3',{},'最近 30 天登录记录'),
            el('div',{class:'login-security-actions'},[el('input',{type:'text',value:filter.value,placeholder:'按账号精确查询','aria-label':'查询账号',onInput:e=>filter.value=e.target.value}),button('查询',()=>{page.value=1;loadRecords()},recordsBusy.value)]),
            el('div',{style:'overflow:auto'},[el('table',{},[el('thead',{},[el('tr',{},['时间','账号','结果','入口','连接地址'].map(t=>el('th',{},t)))]),el('tbody',{},rows.value.map(row=>el('tr',{},[new Date(row.time).toLocaleString(),row.account,results[row.result]||row.result,row.channel,row.peerAddress].map(t=>el('td',{},t)))))])]),
            !rows.value.length?el('p',{},recordsBusy.value?'加载中…':'暂无登录记录'):null,
            el('div',{class:'login-security-actions'},[button('上一页',()=>{page.value--;loadRecords()},page.value<=1||recordsBusy.value),el('span',{},'第 '+page.value+' 页，共 '+total.value+' 条'),button('下一页',()=>{page.value++;loadRecords()},page.value*50>=total.value||recordsBusy.value)])
          ]):null
        ])
      ]):null
    ]);
  }
});
