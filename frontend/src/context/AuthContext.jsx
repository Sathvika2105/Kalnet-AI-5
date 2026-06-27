import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/auth/me')
      .then(res => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    const res = await api.post('/auth/login', formData)
    setUser({ username: res.data.username })
  }

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // ignore server errors on logout
    }
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
