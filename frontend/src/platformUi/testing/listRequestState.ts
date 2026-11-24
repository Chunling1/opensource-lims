import {reactive} from 'vue'
import {AppError} from '../../services/common/errors'
/** Last request wins when permission scope or route changes during a read. */
export function createListRequestState(){
 const state=reactive({loading:false,error:'' as AppError|''});let generation=0
 async function run<T>(fetchRows:()=>Promise<T>,accept:(rows:T)=>void){
  const request=++generation;state.loading=true;state.error=''
  try{const rows=await fetchRows();if(request===generation)accept(rows)}
  catch(e){if(request===generation)state.error=e instanceof AppError?e:new AppError('NETWORK',e instanceof Error?e.message:'检测清单读取失败')}
  finally{if(request===generation)state.loading=false}
 }
 function dispose(){generation++;state.loading=false}
 return {state,run,dispose}
}
