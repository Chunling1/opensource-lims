// Work in cents and thousandths to avoid binary floating-point rounding in totals.
export function calculateLineTotal(price: number | null, quantity: number | null) {
  if (price === null || quantity === null || !Number.isFinite(price) || !Number.isFinite(quantity)) return null
  const cents = Math.round(price * 100), units = Math.round(quantity * 1000)
  if (!Number.isSafeInteger(cents) || !Number.isSafeInteger(units) || cents < 0 || units < 0) return null
  return Number((BigInt(cents) * BigInt(units) + 500n) / 1000n) / 100
}
