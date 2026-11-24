import { AppError } from '../common/errors'
import { platformRequest } from '../platform/http'
import { currentActor } from '../../stores/session'
export interface PersonalDetails { phone:string;email:string;avatar?:string }
export const profileService = {
  async save(expectedActorId:string,input:PersonalDetails) {
    if(expectedActorId!==currentActor.value.id) throw new AppError('FORBIDDEN','登录账号已变化，请重新打开个人资料。')
    return platformRequest<PersonalDetails>('/api/auth/personal-profile',{method:'PUT',body:{phone:input.phone,email:input.email,avatar:input.avatar||''}})
  },
}
