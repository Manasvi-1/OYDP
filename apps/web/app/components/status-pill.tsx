const TONE: Record<string, string> = {
  unverified: 'warn',
  open: 'info',
  closed: 'planned',
  quarantined: 'warn',
  pass: 'ok',
  fail: 'danger',
  current: 'ok',
  superseded: 'planned',
  conflict: 'danger',
  recorded: 'info',
  abstained: 'planned',
  rights_unknown: 'warn',
  implemented: 'ok',
  'partially implemented': 'info',
  prototype: 'warn',
  planned: 'planned',
  blocked: 'danger',
}

export function StatusPill({ label, tone }: { label: string; tone?: string }) {
  const resolved = tone ?? TONE[label.toLowerCase()] ?? 'planned'
  return <span className={`status-pill ${resolved}`}>{label}</span>
}

export function documentStatusLabel(scanState: string) {
  if (scanState === 'pass') return { label: 'Available for authorized download', tone: 'ok' }
  if (scanState === 'fail') return { label: 'Rejected', tone: 'danger' }
  if (scanState === 'quarantined') return { label: 'Quarantined · Scan unavailable', tone: 'warn' }
  return { label: scanState || 'Unknown', tone: 'planned' }
}
