export const ERROR_TEXT: Record<string, string>
export function errorText(code: string | undefined): string
export function parseUuid(value: string): string | null
export function parseCursor(value: string | undefined): string | null
export function pageSize(raw: string | undefined): number | null
export function parsePropertyInput(label: string, jurisdiction: string): { label: string; jurisdiction: string } | null
export function parseStatement(value: string): string | null
