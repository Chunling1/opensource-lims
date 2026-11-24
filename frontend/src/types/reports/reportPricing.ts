export interface ReportPricingTotals {
  standardPrice: number | null
  discountPrice: number | null
  actualPrice: number | null
}
export interface ReportPricingItem extends ReportPricingTotals {
  id: string; name: string; quantity: number | null; discountRate: number | null
}
export interface ReportPricingDetail extends ReportPricingTotals {
  id: string; version: number; releaseId: string
  code: string; testPlan: string; quantity: number
  pricingMethod: string
  parameterItems: ReportPricingItem[]; otherItems: ReportPricingItem[]
}
