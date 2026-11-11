'use client'

export default function WorkspaceError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  void error
  return (
    <section className="panel stack" role="alert">
      <h1>This page could not be loaded</h1>
      <p className="muted">The workspace did not receive a usable response. No property record was changed.</p>
      <p><button className="primary" type="button" onClick={() => reset()}>Try again</button></p>
    </section>
  )
}
