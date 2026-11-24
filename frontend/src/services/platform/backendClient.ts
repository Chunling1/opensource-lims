import { backendCatalog, type BackendEndpoint } from './backendCatalog'
import { platformRequest, type RequestOptions } from './http'
import { AppError } from '../common/errors'
export function backendPath(endpoint: BackendEndpoint, parameters: Record<string,string|number> = {}, query: Record<string,string|number|boolean|undefined> = {}) {
  const contract = backendCatalog[endpoint]
  if (!contract) throw new AppError('BAD_REQUEST','接口未列入平台路由契约。')
  const used = new Set<string>()
  const pathname = contract.path.replace(/<(?:(int|path|string|float|uuid):)?([^>]+)>/g, (_match, kind: string, name: string) => {
    const value=parameters[name]
    if(value===undefined||value===null||value==='') throw new AppError('BAD_REQUEST',`接口缺少路径参数 ${name}。`)
    const text=String(value)
    if(kind==='int' && !/^\d+$/.test(text)) throw new AppError('BAD_REQUEST',`接口路径参数 ${name} 必须是整数。`)
    if(kind!=='path' && /[\/\\\r\n]/.test(text)) throw new AppError('BAD_REQUEST',`接口路径参数 ${name} 含无效字符。`)
    used.add(name)
    return kind==='path'?text.split('/').map(encodeURIComponent).join('/'):encodeURIComponent(text)
  })
  for(const key of Object.keys(parameters)) if(!used.has(key)) throw new AppError('BAD_REQUEST',`接口不接受路径参数 ${key}。`)
  const search=new URLSearchParams()
  for(const [key,value] of Object.entries(query)) if(value!==undefined) search.set(key,String(value))
  return pathname+(search.size?'?'+search:'')
}
/** Uses the platform method/path verbatim. Callers must separately map and validate the business payload. */
export function callBackend<T>(endpoint: BackendEndpoint, args: {parameters?:Record<string,string|number>;query?:Record<string,string|number|boolean|undefined>;body?:unknown;signal?:AbortSignal;blob?:boolean;anonymous?:boolean} = {}): Promise<T> {
  const path=backendPath(endpoint,args.parameters,args.query)
  const options:RequestOptions={method:backendCatalog[endpoint].method,body:args.body,signal:args.signal,blob:args.blob,anonymous:args.anonymous}
  return platformRequest<T>(path,options)
}
