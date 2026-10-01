/*
  Sign-in landing
  ===============
  The Google OAuth callback redirects here with ?token=...&redirect=...
  We store the token, wipe it from the address bar so it is not left in
  history or a shared link, then continue to wherever the customer was.
*/

import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { setToken } from '../api'

export default function SignInCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const handled = useRef(false)

  useEffect(() => {
    if (handled.current) return
    handled.current = true

    const token = searchParams.get('token')
    const redirect = searchParams.get('redirect') || '/'

    if (!token) {
      setError('Sign-in did not complete. Please try again.')
      return
    }

    setToken(token)
    // Scrub the token from the URL before navigating on.
    window.history.replaceState({}, '', window.location.pathname)

    // Only allow same-site relative paths.
    const target = redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
    navigate(target, { replace: true })
  }, [searchParams, navigate])

  return (
    <div className="page narrow">
      <div className="empty-state">
        {error ? (
          <>
            <h2>Sign-in failed</h2>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={() => navigate('/')}>
              Back to the shop
            </button>
          </>
        ) : (
          <p>Completing sign-in…</p>
        )}
      </div>
    </div>
  )
}
