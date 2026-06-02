import { useState } from 'react'
import { useSpamScores } from '../hooks/usePolling'
import api from '../api/client'
import {
  ShieldCheck, ShieldAlert, ShieldX, AlertTriangle,
  ChevronDown, ChevronUp, Send, Users, TrendingUp, TrendingDown
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

function ScoreRing({ score, size = 80 }) {
  const color =
    score <= 20 ? '#10b981'
    : score <= 40 ? '#eab308'
    : score <= 60 ? '#f97316'
    : '#ef4444'
  const r = (size / 2) - 5
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className={`w-full h-full -rotate-90`} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1e293b" strokeWidth="5" />
        <circle
          cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={`${circ - offset} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xl font-bold text-white">{score}</span>
      </div>
    </div>
  )
}

function FindingsList({ findings }) {
  if (!findings || findings.length === 0) return <p className="text-slate-500 text-sm">No issues found.</p>
  return (
    <div className="space-y-2">
      {findings.map((f, i) => (
        <div key={i} className="flex items-start gap-3 text-sm">
          <span className={`mt-0.5 px-1.5 py-0.5 rounded text-xs font-medium shrink-0 ${
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
  )
}

function RecipientRow({ r, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const Icon = scoreIcons[r.label]

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-slate-800 transition-colors"
      >
        <ScoreRing score={r.score} size={40} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-white text-sm font-medium truncate">{r.name}</span>
            <span className="text-slate-500 text-xs truncate">{r.email}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-slate-500 text-xs">{r.company}</span>
          </div>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${scoreColors[r.label]}`}>
          {scoreLabels[r.label]}
        </span>
        <span className="text-slate-400">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-700/50 p-4 space-y-3">
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider">Subject</label>
            <p className="text-white text-sm mt-1">{r.subject}</p>
          </div>
          {r.body && (
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wider">Body</label>
              <pre className="text-slate-300 mt-1 whitespace-pre-wrap text-sm font-sans leading-relaxed">{r.body}</pre>
            </div>
          )}
          {!r.body && (
            <p className="text-slate-500 text-xs italic">Body not stored (pipeline needs to run to capture it)</p>
          )}
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider">Findings</label>
            <div className="mt-2">
              <FindingsList findings={r.findings} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StepCard({ template }) {
  const [open, setOpen] = useState(false)
  const recipients = template.recipients || []
  const sorted = [...recipients].sort((a, b) => b.score - a.score)
  const Icon = scoreIcons[
    template.avg_score <= 20 ? 'safe' :
    template.avg_score <= 40 ? 'low_risk' :
    template.avg_score <= 60 ? 'medium_risk' : 'high_risk'
  ]

  return (
    <div className="bg-card rounded-xl border border-slate-700 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full p-5 flex items-center gap-4 text-left hover:bg-slate-800/50 transition-colors"
      >
        <ScoreRing score={template.avg_score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Icon size={16} className={scoreColors[
              template.avg_score <= 20 ? 'safe' :
              template.avg_score <= 40 ? 'low_risk' :
              template.avg_score <= 60 ? 'medium_risk' : 'high_risk'
            ].split(' ')[0]} />
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${scoreColors[
              template.avg_score <= 20 ? 'safe' :
              template.avg_score <= 40 ? 'low_risk' :
              template.avg_score <= 60 ? 'medium_risk' : 'high_risk'
            ]}`}>
              Avg Score
            </span>
          </div>
          <h3 className="text-white font-semibold">Email #{template.step}</h3>
          <p className="text-slate-400 text-sm">
            {template.recipient_count} recipient{template.recipient_count !== 1 ? 's' : ''} sent
          </p>
        </div>
        <div className="text-right mr-2">
          <div className="flex items-center gap-1 text-emerald-400 text-xs">
            <TrendingDown size={14} />
            <span>{template.best?.score} best</span>
          </div>
          <div className="flex items-center gap-1 text-red-400 text-xs mt-1">
            <TrendingUp size={14} />
            <span>{template.worst?.score} worst</span>
          </div>
        </div>
        <span className="text-slate-400">
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-700 p-5 space-y-4">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5 text-slate-400">
              <Users size={14} />
              <span>{template.recipient_count} recipient{template.recipient_count !== 1 ? 's' : ''}</span>
            </div>
            <div className="text-slate-500">|</div>
            <div className="text-slate-400">
              Avg: <span className="text-white font-medium">{template.avg_score}</span>/100
            </div>
            <div className="text-slate-500">|</div>
            <div className="text-emerald-400">
              Best: <span className="font-medium">{template.best?.name}</span> ({template.best?.score})
            </div>
            <div className="text-red-400">
              Worst: <span className="font-medium">{template.worst?.name}</span> ({template.worst?.score})
            </div>
          </div>

          <div className="space-y-2">
            {sorted.map(r => (
              <RecipientRow key={r.lead_id} r={r} defaultOpen={r.score >= 30} />
            ))}
          </div>
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
          <FindingsList findings={result.findings} />
        </div>
      )}
    </div>
  )
}

export default function SpamScore() {
  const { data, loading, error } = useSpamScores()
  const templates = data?.templates || []

  const totalRecipients = templates.reduce((s, t) => s + t.recipient_count, 0)
  const overallAvg = totalRecipients > 0
    ? Math.round(templates.reduce((s, t) => s + t.avg_score * t.recipient_count, 0) / totalRecipients)
    : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Spam Score Checker</h1>
        <p className="text-slate-400 text-sm mt-1">Analyze actual emails sent through the pipeline</p>
      </div>

      {loading && <div className="text-slate-400 text-sm">Loading spam scores...</div>}
      {error && <div className="text-red-400 text-sm">Failed to load spam scores.</div>}

      {!loading && !error && templates.length === 0 && (
        <div className="bg-card rounded-xl border border-slate-700 p-8 text-center">
          <ShieldCheck size={48} className="mx-auto text-slate-600 mb-4" />
          <h3 className="text-white font-semibold mb-2">No sent emails yet</h3>
          <p className="text-slate-400 text-sm">Run the pipeline to send emails, then come back to check spam scores.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card rounded-xl border border-slate-700 p-5">
          <span className="text-slate-400 text-sm">Overall Avg Score</span>
          <div className="flex items-end gap-2 mt-2">
            <span className="text-3xl font-bold text-white">{overallAvg}</span>
            <span className="text-slate-500 text-sm mb-1">/ 100</span>
          </div>
        </div>
        <div className="bg-card rounded-xl border border-slate-700 p-5">
          <span className="text-slate-400 text-sm">Total Recipients</span>
          <div className="flex items-end gap-2 mt-2">
            <span className="text-3xl font-bold text-white">{totalRecipients}</span>
          </div>
        </div>
        {templates.map(t => {
          const label =
            t.avg_score <= 20 ? 'safe' :
            t.avg_score <= 40 ? 'low_risk' :
            t.avg_score <= 60 ? 'medium_risk' : 'high_risk'
          return (
            <div key={t.step} className="bg-card rounded-xl border border-slate-700 p-5">
              <span className="text-slate-400 text-sm">Email #{t.step}</span>
              <div className="flex items-end gap-2 mt-2">
                <span className="text-3xl font-bold text-white">{t.avg_score}</span>
                <span className="text-slate-500 text-sm mb-1">avg</span>
              </div>
              <span className={`inline-block mt-2 text-xs font-medium px-2 py-0.5 rounded-full border ${scoreColors[label]}`}>
                {scoreLabels[label]} · {t.recipient_count}
              </span>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">By Email Sequence</h2>
          {templates.map(t => (
            <StepCard key={t.step} template={t} />
          ))}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Custom Check</h2>
          <CustomChecker />
        </div>
      </div>
    </div>
  )
}
