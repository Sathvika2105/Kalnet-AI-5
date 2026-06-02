import { useState, useEffect, useCallback, useRef } from 'react'
import api from '../api/client'

const POLL_INTERVAL = 30000

export function usePolling(fetchFn, interval = POLL_INTERVAL) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const intervalRef = useRef(null)

  const fetchData = useCallback(async () => {
    try {
      const result = await fetchFn()
      setData(result)
      setLastUpdated(new Date())
      setError(null)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [fetchFn])

  useEffect(() => {
    fetchData()
    intervalRef.current = setInterval(fetchData, interval)
    return () => clearInterval(intervalRef.current)
  }, [fetchData, interval])

  const refresh = useCallback(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, lastUpdated, refresh }
}

export function useMetrics() {
  const fetchFn = useCallback(async () => {
    const res = await api.get('/metrics')
    return res.data
  }, [])
  return usePolling(fetchFn)
}

export function useLeads(filters = {}) {
  const fetchFn = useCallback(async () => {
    const params = {}
    if (filters.replied) params.replied = filters.replied
    if (filters.opt_out) params.opt_out = filters.opt_out
    if (filters.step) params.step = filters.step
    const res = await api.get('/leads', { params })
    return res.data
  }, [filters.replied, filters.opt_out, filters.step])
  return usePolling(fetchFn)
}

export function useReplies() {
  const fetchFn = useCallback(async () => {
    const res = await api.get('/replies')
    return res.data
  }, [])
  return usePolling(fetchFn)
}

export function useAnalytics() {
  const fetchFn = useCallback(async () => {
    const res = await api.get('/analytics')
    return res.data
  }, [])
  return usePolling(fetchFn)
}

export function useSubjectLines() {
  const fetchFn = useCallback(async () => {
    const res = await api.get('/subject-lines')
    return res.data
  }, [])
  return usePolling(fetchFn)
}
