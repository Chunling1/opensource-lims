import type { InjectionKey, Ref } from 'vue'

export const feedbackTargetKey: InjectionKey<Ref<HTMLElement | undefined>> = Symbol('feedback-target')
export const insideToastKey: InjectionKey<boolean> = Symbol('inside-toast')
