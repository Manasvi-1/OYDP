export default function LoadingWorkspace() {
  return (
    <section className="panel stack" role="status" aria-live="polite">
      <h1>Loading workspace records</h1>
      <p className="muted">Reading only the records this session is allowed to see.</p>
    </section>
  )
}
