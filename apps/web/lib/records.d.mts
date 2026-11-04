export interface PropertyView {
  id: string
  label: string
  jurisdiction: string
  createdBy: string
  createdAt: string
}
export interface ClaimView {
  id: string
  statement: string
  createdBy: string
  recordedAt: string
  status: string
}
export function propertyRecord(value: unknown): PropertyView | null
export function claimRecord(value: unknown): ClaimView | null
export function propertyPage(value: unknown): { items: PropertyView[]; nextCursor: string | null } | null
export function claimPage(value: unknown): { items: ClaimView[]; nextCursor: string | null } | null
export function formatWhen(value: string): string
