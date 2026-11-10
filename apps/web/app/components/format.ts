export function formatWhen(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function shortId(value: string) {
  if (!value || value.length < 12) return value
  return `${value.slice(0, 8)}…${value.slice(-4)}`
}

export function bounded(value: string | undefined, max = 300) {
  return value ? value.slice(0, max) : ''
}
