import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="status-card">
      <h1>404 — Not found</h1>
      <p className="muted">This page doesn't exist yet (or at all).</p>
      <Link to="/">Back to status</Link>
    </div>
  )
}
