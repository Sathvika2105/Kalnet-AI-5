import { useState, useEffect, useRef } from 'react'
import api from '../api/client'
import { useToast } from '../context/ToastContext'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { playSuccessSound, playErrorSound } from '../utils/sounds'
import ConfirmDialog from '../components/ConfirmDialog'
import { SkeletonPage } from '../components/Skeleton'
import { Save, Play, FileText, Loader2, XCircle } from 'lucide-react'

export default function Settings() {
  const { addToast } = useToast()
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [logType, setLogType] = useState('pipeline')
  const [logContent, setLogContent] = useState('')
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [logStreaming, setLogStreaming] = useState(false)
  const pollRef = useRef(null)
  const logPollRef = useRef(null)
  const logContainerRef = useRef(null)

  useEffect(() => {
    api.get('/settings').then(res => {
      setSettings(res.data)
      setLoading(false)
    }).catch(() => {
      addToast('Failed to load settings', 'error')
      setLoading(false)
    })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/settings', settings)
      playSuccessSound()
      addToast('Settings saved successfully', 'success')
    } catch {
      playErrorSound()
      addToast('Failed to save settings', 'error')
    }
    setSaving(false)
  }

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (logPollRef.current) clearInterval(logPollRef.current)
    }
  }, [])

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logContent])

  const loadLogs = async () => {
    const res = await api.get(`/logs/${logType}`)
    setLogContent(res.data.content)
    if (running && !logPollRef.current) {
      setLogStreaming(true)
      logPollRef.current = setInterval(async () => {
        try {
          const res = await api.get(`/logs/${logType}`)
          setLogContent(res.data.content)
        } catch {
          // ignore
        }
      }, 3000)
    }
  }

  useEffect(() => {
    if (!running) {
      if (logPollRef.current) {
        clearInterval(logPollRef.current)
        logPollRef.current = null
      }
      setLogStreaming(false)
    }
  }, [running])

  useKeyboardShortcuts([
    { key: 'l', handler: () => loadLogs(), allowInput: false },
    { key: 'Enter', ctrl: true, handler: () => handleSave(), allowInput: true },
  ])

  const handleRunPipeline = async () => {
    setShowConfirm(false)
    setRunning(true)
    setRunResult({ success: true, message: 'Pipeline is running...' })
    try {
      await api.post('/pipeline/run')
      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get('/pipeline/status')
          if (!data.running) {
            clearInterval(pollRef.current)
            pollRef.current = null
            setRunning(false)
            if (data.success) {
              setRunResult({ success: true, message: data.message })
              playSuccessSound()
              addToast('Pipeline completed successfully', 'success')
            } else {
              const errMsg = data.error || 'Unknown error'
              setRunResult({ success: false, message: `Pipeline failed: ${errMsg}` })
              playErrorSound()
              addToast(errMsg, 'error', 8000)
            }
          }
        } catch {
          clearInterval(pollRef.current)
          pollRef.current = null
          setRunning(false)
          setRunResult({ success: false, message: 'Failed to check pipeline status' })
        }
      }, 2000)
    } catch (err) {
      setRunning(false)
      const msg = err.response?.data?.error || 'Pipeline failed'
      setRunResult({ success: false, message: msg })
      addToast(msg, 'error', 8000)
    }
  }

  const handleChange = (key, value) => {
    setSettings({ ...settings, [key]: value })
  }

  if (loading) return <SkeletonPage />

  return (
    <div className="space-y-8">
      <ConfirmDialog
        isOpen={showConfirm}
        title="Run Pipeline"
        message="Are you sure you want to trigger the email automation pipeline? This will check for replies and send scheduled emails."
        confirmLabel="Run Pipeline"
        variant="warning"
        onConfirm={handleRunPipeline}
        onCancel={() => setShowConfirm(false)}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-slate-400 mt-1">Configure pipeline and email settings</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400">R</kbd>
          <span>Run pipeline</span>
          <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 ml-2">L</kbd>
          <span>Load logs</span>
          <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-400 ml-2">Ctrl+Enter</kbd>
          <span>Save</span>
        </div>
      </div>

      {/* Run Pipeline Section */}
      <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 rounded-xl border border-blue-500/30 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Run Pipeline Now</h3>
            <p className="text-sm text-slate-400 mt-1">Trigger the email automation pipeline manually</p>
          </div>
          <button
            onClick={() => setShowConfirm(true)}
            disabled={running}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
          >
            {running ? (
              <>
                <Loader2 size={20} className="animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play size={20} />
                Run Pipeline
              </>
            )}
          </button>
        </div>

        {running && (
          <div className="mt-4 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
            <div className="bg-blue-500 h-full rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
        )}

        {runResult && (
          <div className={`mt-4 p-3 rounded-lg flex items-center gap-2 ${
            runResult.success && !running
              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : runResult.success && running
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/30'
          }`}>
            {runResult.success ? <Loader2 size={18} className={running ? 'animate-spin' : ''} /> : <XCircle size={18} />}
            <span className="text-sm">{runResult.message}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card-bg rounded-xl border border-card-border p-6 space-y-6">
          <h3 className="text-lg font-semibold text-white">Pipeline Configuration</h3>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Delay Between Emails (seconds)</label>
            <input
              type="number"
              value={settings.delay_between_emails != null ? settings.delay_between_emails : ''}
              onChange={(e) => handleChange('delay_between_emails', e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Max Emails Per Run</label>
            <input
              type="number"
              value={settings.max_emails_per_run != null ? settings.max_emails_per_run : ''}
              onChange={(e) => handleChange('max_emails_per_run', e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Email 1 (Days)</label>
              <input
                type="number"
                value={settings.email_1_delay_days != null ? settings.email_1_delay_days : ''}
                onChange={(e) => handleChange('email_1_delay_days', e.target.value)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Email 2 (Days)</label>
              <input
                type="number"
                value={settings.email_2_delay_days != null ? settings.email_2_delay_days : ''}
                onChange={(e) => handleChange('email_2_delay_days', e.target.value)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Email 3 (Days)</label>
              <input
                type="number"
                value={settings.email_3_delay_days != null ? settings.email_3_delay_days : ''}
                onChange={(e) => handleChange('email_3_delay_days', e.target.value)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
              />
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
          >
            <Save size={18} />
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>

        <div className="bg-card-bg rounded-xl border border-card-border p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Pipeline Logs</h3>
            {logStreaming && (
              <span className="flex items-center gap-1.5 text-xs text-green-400 font-medium">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                LIVE
              </span>
            )}
          </div>

          <div className="flex gap-4">
            <select
              value={logType}
              onChange={(e) => setLogType(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm"
            >
              <option value="pipeline">Pipeline Log</option>
            </select>

            <button
              onClick={loadLogs}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
            >
              <FileText size={16} />
              {logStreaming ? 'Streaming...' : 'Load'}
            </button>
          </div>

          <pre
            ref={logContainerRef}
            className="bg-slate-900 rounded-lg p-4 text-sm text-slate-300 overflow-auto max-h-96 font-mono"
          >
            {logContent || 'Click "Load" to view logs'}
          </pre>
        </div>
      </div>
    </div>
  )
}
