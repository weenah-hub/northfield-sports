import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="page narrow">
      <div className="empty-state">
        <span className="empty-icon" aria-hidden="true">🔍</span>
        <h1>Page not found</h1>
        <p>That link does not lead anywhere.</p>
        <Link className="btn btn-primary" to="/">
          Back to the shop
        </Link>
      </div>
    </div>
  )
}
