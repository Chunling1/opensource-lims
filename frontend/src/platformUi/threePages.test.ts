import {beforeEach,describe,it,expect,vi} from 'vitest'
import {profile} from '../services/platform/auth'
import {setToken,getSessionToken} from '../services/platform/http'
import {currentActor} from '../stores/session'
import {signIn,queryLoginState,checkCaptcha,changeAccountPassword} from '../services/auth/authApi'
import {profileService} from '../services/auth/profileService'
import {allowedWorkbench} from '../types/dashboard'
const actor={account:'fixture',userName:'测试',roleKey:'tester',roleName:'检测',homePath:'/dashboard',dataScope:{department:'测试科',scopeType:'self' as const,description:'本人'},permissions:['testing.data_entry.view'],actionPermissions:[],personal:{phone:'',email:'',avatar:'',departmentName:'测试科',position:'',jobTitle:'',certificateNumber:''}}
const respond=(data:unknown)=>new Response(JSON.stringify({code:0,data}),{headers:{'content-type':'application/json'}})
beforeEach(()=>{profile.value=undefined;setToken('');vi.restoreAllMocks()})
describe('supplied UI uses platform contracts',()=>{
 it('consumes CAPTCHA proof on login and loads the real profile',async()=>{
  const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValueOnce(respond({...actor,token:'fixture-token'})).mockResolvedValueOnce(respond(actor))
  await signIn(' fixture ','Fixture123!',false,'one-use-proof')
  expect(JSON.parse(String(fetcher.mock.calls[0]![1]!.body))).toMatchObject({account:'fixture',captchaVerification:'one-use-proof'})
  expect(getSessionToken()).toBe('fixture-token');expect(currentActor.value.id).toBe('fixture')
  expect(allowedWorkbench(currentActor.value,'analyst')).toBe(true);expect(allowedWorkbench(currentActor.value,'reviewer')).toBe(false)
 })
 it('saves only own editable contact fields',async()=>{
  currentActor.value={id:'fixture',name:'测试',roles:[],departmentId:'',scope:'department'}
  const details={phone:'13900000000',email:'fixture@example.invalid',avatar:''}
  const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValue(respond(details))
  await expect(profileService.save('another',details)).rejects.toThrow()
  expect(fetcher).not.toHaveBeenCalled()
  await profileService.save('fixture',details)
  expect(fetcher.mock.calls[0]![0]).toBe('/api/auth/personal-profile')
  expect(JSON.parse(String(fetcher.mock.calls[0]![1]!.body))).toEqual(details)
 })
 it('propagates CAPTCHA failures and rejects anonymous password changes without proof',async()=>{
  const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({repCode:'FAILED',repMsg:'验证失效'}),{headers:{'content-type':'application/json'}}))
  await expect(checkCaptcha('fixture','token','ciphertext','blockPuzzle')).rejects.toThrow('验证失效')
  fetcher.mockClear();await expect(changeAccountPassword('fixture','old','NewSecret123!','NewSecret123!','')).rejects.toThrow('请先完成安全验证')
  expect(fetcher).not.toHaveBeenCalled()
 })
 it('changes the signed-in password without CAPTCHA and clears the session',async()=>{
  setToken('fixture-session')
  const fetcher=vi.spyOn(globalThis,'fetch').mockResolvedValue(respond(null))
  await changeAccountPassword('fixture','OldSecret123!','NewSecret123!','NewSecret123!')
  expect(new Headers(fetcher.mock.calls[0]![1]!.headers).get('Authorization')).toBe('Bearer fixture-session')
  const body=JSON.parse(String(fetcher.mock.calls[0]![1]!.body))
  expect(body).toMatchObject({account:'fixture',oldPassword:'OldSecret123!',newPassword:'NewSecret123!'})
  expect(body).not.toHaveProperty('captchaVerification')
  expect(getSessionToken()).toBe('')
 })
 it('keeps password strength and confirmation checks for signed-in changes',async()=>{
  setToken('fixture-session')
  const fetcher=vi.spyOn(globalThis,'fetch')
  await expect(changeAccountPassword('fixture','old','weak','weak')).rejects.toThrow('新密码须包含或满足')
  await expect(changeAccountPassword('fixture','old','NewSecret123!','different')).rejects.toThrow('两次输入')
  expect(fetcher).not.toHaveBeenCalled()
 })
})
