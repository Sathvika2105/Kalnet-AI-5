import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import { Save, Play, FileText, Loader2, CheckCircle, XCircle } from 'lucide-react'

export default function Settings() {
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [logType, setLogType] = useState('pipeline')
  const [logContent, setLogContent] = useState('')
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState(null)

  useEffect(() => {
    api.get('/settings').then(res => {
      setSettings(res.data)
      setLoading(false)
    })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    await api.put('/settings', settings)
    setSaving(false)
    alert('Settings saved!')
  }

  const handleRunPipeline = async () => {
    setRunning(true)
    setRunResult(null)
    try {
      const res = await api.post('/pipeline/run')
      setRunResult({ success: true, message: res.data.message })
    } catch (err) {
      setRunResult({ success: false, message: err.response?.data?.error || 'Pipeline failed' })
    } finally {
      setRunning(false)
    }
  }

  const loadLogs = async () => {
    const res = await api.get(`/logs/${logType}`)
    setLogContent(res.data.content)
  }

  const handleChange = (key, value) => {
    setSettings({ ...settings, [key]: value })
  }

  if (loading) return <div className="text-slate-400">Loading...</div>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-slate-400 mt-1">Configure pipeline and email settings</p>
      </div>

      {/* Run Pipeline Section */}
      <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 rounded-xl border border-blue-500/30 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Run Pipeline Now</h3>
            <p className="text-sm text-slate-400 mt-1">Trigger the email automation pipeline manually</p>
          </div>
          <button
            onClick={handleRunPipeline}
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

        {runResult && (
          <div className={`mt-4 p-3 rounded-lg flex items-center gap-2 ${
            runResult.success
              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/30'
          }`}>
            {runResult.success ? <CheckCircle size={18} /> : <XCircle size={18} />}
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
              value={settings.delay_between_emails || ''}
              onChange={(e) => handleChange('delay_between_emails', e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Max Emails Per Run</label>
            <input
              type="number"
              value={settings.max_emails_per_run || ''}
              onChange={(e) => handleChange('max_emails_per_run', e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Email 1 (Days)</label>
              <input
                type="number"
                value={settings.email_1_delay_days || ''}
                onChange={(e) => handleChange('email_1_delay_days', e.target.value)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Email 2 (Days)</label>
              <input
                type="number"
                value={settings.email_2_delay_days || ''}
                onChange={(e) => handleChange('email_2_delay_days', e.target.value)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Email 3 (Days)</label>
              <input
                type="number"
                value={settings.email_3_delay_days || ''}
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
          <h3 className="text-lg font-semibold text-white">Pipeline Logs</h3>

          <div className="flex gap-4">
            <select
              value={logType}
              onChange={(e) => setLogType(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm"
            >
              <option value="pipeline">Pipeline Log</option>
              <option value="email">Email Log</option>
              <option value="replies">Replies Log</option>
              <option value="sequence">Sequence Log</option>
              <option value="replies_summary">Replies Summary</option>
            </select>

            <button
              onClick={loadLogs}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
            >
              <FileText size={16} />
              Load
            </button>
          </div>

          <pre className="bg-slate-900 rounded-lg p-4 text-sm text-slate-300 overflow-auto max-h-64 font-mono">
            {logContent || 'Click "Load" to view logs'}
          </pre>
        </div>
      </div>
    </div>
  )
}
