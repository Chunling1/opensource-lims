/** Number restrictions apply to incoming Erp projects, not locally saved agreements. */
export function isVisibleContractNumber(value: unknown): boolean {
  return typeof value === 'string' && /^[0-9]{4}03013[123]/.test(value.trim())
}
type AgreementSource = { id?: number; agreementNo: string; info?: { fromErp?: string } }
export function isVisibleAgreement(row: AgreementSource): boolean {
  return (!!row.id && row.info?.fromErp !== '1') || isVisibleContractNumber(row.agreementNo)
}
type ContractRow = { contractNo: string; agreement?: AgreementSource }
export function visibleContractRows<T extends ContractRow>(rows: T[]): T[] {
  return rows.filter(row => row.agreement ? isVisibleAgreement(row.agreement) : isVisibleContractNumber(row.contractNo))
}
/** Unnumbered drafts need distinct selection keys; never use this key as a business number. */
export function contractRowKey(row: ContractRow): string {
  return row.contractNo || `agreement:${row.agreement?.id}`
}
