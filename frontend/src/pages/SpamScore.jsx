import { useState } from 'react'
import { useSpamScores } from '../hooks/usePolling'
import api from '../api/client'
import {
  ShieldCheck, ShieldAlert, ShieldX, AlertTriangle,
  ChevronDown, ChevronUp, Send
} from 'lucide-react'

const scoreColors = {
  safe: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  low_risk: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  medium_risk: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
  high_risk: 'text-red-400 bg-red-500/10 border-red-500/20',
}

const scoreLabels = {
  safe: 'Safe',
  low_risk: 'Low Risk',
  medium_risk: 'Medium Risk',
  high_risk: 'High Risk',
}

const scoreIcons = {
  safe: ShieldCheck,
  low_risk: ShieldAlert,
  medium_risk: AlertTriangle,
  high_risk: ShieldX,
}

function ScoreRing({ score }) {
  const color =
    score <= 20 ? '#10b981'
    : score <= 40 ? '#eab308'
    : score <= 60 ? '#f97316'
    : '#ef4444'

  return (
    <div className="relative w-20 h-20">
      <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="35" fill="none" stroke="#1e293b" strokeWidth="6" />
        <circle
          cx="40" cy="40" r="35" fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${(score / 100) * 220} 220`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xl font-bold text-white">{score}</span>
      </div>
    </div>
  )
}

function TemplateCard({ template }) {
  const [open, setOpen] = useState(false)
  const Icon = scoreIcons[template.label]
  const findings = template.findings || []

  return (
    <div className="bg-card rounded-xl border border-slate-700 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full p-5 flex items-center gap-4 text-left hover:bg-slate-800/50 transition-colors"
      >
        <ScoreRing score={template.score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Icon size={16} className={scoreColors[template.label].split(' ')[0]} />
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${scoreColors[template.label]}`}>
              {scoreLabels[template.label]}
            </span>
          </div>
          <h3 className="text-white font-semibold">Email #{template.step}</h3>
          <p className="text-slate-400 text-sm truncate">{template.subject}</p>
        </div>
        <div className="text-slate-400">
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
      </button>

      {open && (
        <div className="border-t border-slate-700 p-5 space-y-4">
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider">Subject</label>
            <p className="text-white mt-1">{template.subject}</p>
          </div>
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider">Body</label>
            <pre className="text-slate-300 mt-1 whitespace-pre-wrap text-sm font-sans leading-relaxed">{template.body}</pre>
          </div>
          {findings.length > 0 && (
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wider">Findings</label>
              <div className="mt-2 space-y-2">
                {findings.map((f, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm">
                    <span className={`mt-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${
                      f.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                      f.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                      f.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                      f.severity === 'low' ? 'bg-slate-500/20 text-slate-400' :
                      'bg-blue-500/20 text-blue-400'
                    }`}>
                      {f.points > 0 ? `+${f.points}` : '—'}
                    </span>
                    <span className={f.points > 0 ? 'text-slate-300' : 'text-slate-500'}>{f.rule}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function CustomChecker() {
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleCheck = async () => {
    if (!subject && !body) return
    setLoading(true)
    try {
      const res = await api.post('/spam-score', { subject, body })
      setResult(res.data)
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-card rounded-xl border border-slate-700 p-6 space-y-4">
      <h3 className="text-white font-semibold text-lg">Custom Email Check</h3>
      <div>
        <label className="text-xs text-slate-500 uppercase tracking-wider">Subject</label>
        <input
          type="text"
          value={subject}
          onChange={e => setSubject(e.target.value)}
          placeholder="Enter subject line..."
          className="w-full mt-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
        />
      </div>
      <div>
        <label className="text-xs text-slate-500 uppercase tracking-wider">Body</label>
        <textarea
          value={body}
          onChange={e => setBody(e.target.value)}
          placeholder="Enter email body..."
          rows={6}
          className="w-full mt-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm resize-none"
        />
      </div>
      <button
        onClick={handleCheck}
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors text-sm font-medium"
      >
        <Send size={16} />
        {loading ? 'Checking...' : 'Check Spam Score'}
      </button>

      {result && (
        <div className="border-t border-slate-700 pt-4 space-y-3">
          <div className="flex items-center gap-3">
            <ScoreRing score={result.score} />
            <div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${scoreColors[result.label]}`}>
                {scoreLabels[result.label]}
              </span>
              <p className="text-slate-400 text-sm mt-1">
                {result.score <= 20 ? 'Your email looks safe to send.' :
                 result.score <= 40 ? 'Low risk — consider minor improvements.' :
                 result.score <= 60 ? 'Medium risk — review findings below.' :
                 'High risk — likely to trigger spam filters.'}
              </p>
            </div>
          </div>
          {result.findings.length > 0 && (
            <div className="space-y-2">
              {result.findings.map((f, i) => (
                <div key={i} className="flex items-start gap-3 text-sm">
                  <span className={`mt-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${
                    f.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                    f.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                    f.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                    f.severity === 'low' ? 'bg-slate-500/20 text-slate-400' :
                    'bg-blue-500/20 text-blue-400'
                  }`}>
                    {f.points > 0 ? `+${f.points}` : '—'}
                  </span>
                  <span className={f.points > 0 ? 'text-slate-300' : 'text-slate-500'}>{f.rule}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function SpamScore() {
  const { data, loading, error } = useSpamScores()
  const templates = data?.templates || []

  const avgScore = templates.length
    ? Math.round(templates.reduce((s, t) => s + t.score, 0) / templates.length)
    : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Spam Score Checker</h1>
        <p className="text-slate-400 text-sm mt-1">Analyze email templates against spam rules</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'Email #1 (Day 0)', color: 'blue' },
          { label: 'Email #2 (Day 5)', color: 'yellow' },
          { label: 'Email #3 (Day 10)', color: 'purple' },
        ].map((item, i) => {
          const t = templates[i]
          if (!t) return null
          const Icon = scoreIcons[t.label]
          return (
            <div key={i} className="bg-card rounded-xl border border-slate-700 p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-slate-400 text-sm">{item.label}</span>
                <Icon size={18} className={scoreColors[t.label].split(' ')[0]} />
              </div>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-bold text-white">{t.score}</span>
                <span className="text-slate-500 text-sm mb-1">/ 100</span>
              </div>
              <span className={`inline-block mt-2 text-xs font-medium px-2 py-0.5 rounded-full border ${scoreColors[t.label]}`}>
                {scoreLabels[t.label]}
              </span>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Email Templates</h2>
          {loading && <div className="text-slate-400 text-sm">Loading...</div>}
          {error && <div className="text-red-400 text-sm">Failed to load spam scores.</div>}
          {templates.map(t => (
            <TemplateCard key={t.step} template={t} />
          ))}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Check Your Own</h2>
          <CustomChecker />
        </div>
      </div>
    </div>
  )
}
