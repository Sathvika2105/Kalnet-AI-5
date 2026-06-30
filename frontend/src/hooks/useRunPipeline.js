import { useState, useRef, useEffect, useCallback } from 'react'
import api from '../api/client'
import { useToast } from '../context/ToastContext'
import { playSuccessSound, playErrorSound } from '../utils/sounds'

export function useRunPipeline({ onComplete } = {}) {
  const { addToast } = useToast()
  const [running, setRunning] = useState(false)
  const [pipelineMsg, setPipelineMsg] = useState('')
  const pollRef = useRef(null)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const run = useCallback(async () => {
    setRunning(true)
    setPipelineMsg('Running...')
    try {
      await api.post('/pipeline/run')
      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get('/pipeline/status')
          if (!data.running) {
            clearInterval(pollRef.current)
            pollRef.current = null
            setRunning(false)
            setPipelineMsg('')
            if (data.success) {
              playSuccessSound()
              addToast('Pipeline completed successfully', 'success')
            } else {
              playErrorSound()
              addToast(data.error || 'Pipeline failed', 'error', 8000)
              setPipelineMsg('Failed')
            }
            if (onCompleteRef.current) onCompleteRef.current(data)
          }
        } catch {
          clearInterval(pollRef.current)
          pollRef.current = null
          setRunning(false)
          setPipelineMsg('')
        }
      }, 2000)
    } catch {
      setRunning(false)
      setPipelineMsg('Failed to trigger')
    }
  }, [addToast])

  return { running, pipelineMsg, run }
}
