/*
  Auth context
  ============
  Holds the signed-in user. The JWT itself lives in localStorage (see api.js);
  this provider mirrors it into React state and revalidates it on load.
*/

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, clearToken, getToken } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // "loading" until the stored token has been checked, so the UI can avoid
  // flashing a signed-out header before we know who the user is.
  const [initialising, setInitialising] = useState(Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) {
      setInitialising(false)
      return
    }

    let cancelled = false

    api
      .me()
      .then((data) => {
        if (!cancelled) setUser(data)
      })
      .catch(() => {
        // Expired or invalid token — drop it and treat the visitor as signed out.
        clearToken()
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setInitialising(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const signOut = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, initialising, signOut, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
