export interface DemoPasswordDigest { salt: string; hash: string }
export interface LoginState { captchaRequired: boolean }
export type CaptchaType = 'blockPuzzle' | 'clickWord'
export interface CaptchaImage {
  captchaType: CaptchaType
  originalImageBase64: string
  jigsawImageBase64: string
  wordList?: string[]
  token: string
  secretKey: string
  expiresAt: number
}
export interface CaptchaResponse<T> { repCode: string; repMsg: string; repData?: T; success: boolean; error: boolean }
export interface DemoLoginInput {
  account: string
  password: string
  clientUid: string
  captchaVerification?: string
  // Browser-owned demo settings, not credentials from a production identity provider.
  demoCredential?: DemoPasswordDigest
  accountEnabled: boolean
}
