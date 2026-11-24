type ValidatableControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
export interface FormIssue { control: ValidatableControl; message: string }
export function isValidatableControl(element: EventTarget | null): element is ValidatableControl {
  return element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement
}

/** Include business pickers in the same ordered validation pass as native controls. */
export function formIssues(form: HTMLFormElement, customErrors: Readonly<Record<string, string>> = {}): FormIssue[] {
  const issues = Array.from(form.elements).filter(isValidatableControl).flatMap(control => {
    if (!control.id || control.matches(':disabled') || control instanceof HTMLInputElement && control.type === 'hidden') return []
    let message = customErrors[control.id]
    if (!message && control.willValidate && !control.validity.valid) {
      const label = control.labels?.[0]?.textContent?.replace(/\s*\*\s*$/, '').trim() || '此项'
      message = control.validity.valueMissing
        ? `${control instanceof HTMLSelectElement ? '请选择' : '请填写'}${label}。`
        : control.validationMessage
    }
    return message ? [{ control, message }] : []
  })
  // Visible controls follow their grid positions; hidden tab panels are handled afterwards.
  const positions = new Map(issues.map(issue => [issue.control, issue.control.getClientRects().length ? issue.control.getBoundingClientRect() : undefined]))
  return issues.sort((a, b) => {
    const left = positions.get(a.control), right = positions.get(b.control)
    if (!left || !right) return left ? -1 : right ? 1 : 0
    return left.top - right.top || left.left - right.left
  })
}
