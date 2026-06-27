import { useState } from 'react'
import { useSubjectLines } from '../hooks/usePolling'
import api from '../api/client'
import EmptyState from '../components/EmptyState'
import { SkeletonPage } from '../components/Skeleton'
import { RefreshCw, Mail, BarChart3 } from 'lucide-react'

const EMAIL_TEMPLATES = {
  1: { label: 'Email #1 - Quick Intro', color: 'bg-blue-600/20 text-blue-400' },
  2: { label: 'Email #2 - Follow-up', color: 'bg-purple-600/20 text-purple-400' },
  3: { label: 'Email #3 - Last Follow-up', color: 'bg-orange-600/20 text-orange-400' },
}

export default function SubjectLines() {
  const { data: subjectsData, loading, lastUpdated, refresh } = useSubjectLines()
  const [sentEmails, setSentEmails] = useState([])
  const [emailsLoading, setEmailsLoading] = useState(false)
  const [showEmails, setShowEmails] = useState(false)

  const subjects = subjectsData?.subject_lines || []

  const loadSentEmails = async () => {
    setEmailsLoading(true)
    try {
      const res = await api.get('/leads')
      const sent = (res.data.leads || [])
        .filter(l => l.email_sent_at)
        .sort((a, b) => (b.email_sent_at_raw || b.email_sent_at || '').localeCompare(a.email_sent_at_raw || a.email_sent_at || ''))
      setSentEmails(sent)
      setShowEmails(true)
    } finally {
      setEmailsLoading(false)
    }
  }

  if (loading) return <SkeletonPage />

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Sent Emails</h1>
          <p className="text-slate-400 mt-1">
            What was sent to each client
            {lastUpdated && (
              <span className="text-xs text-slate-500 ml-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => { refresh(); if (showEmails) loadSentEmails() }}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg transition-colors text-sm"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Sent Emails Table */}
      {!showEmails ? (
        <button
          onClick={loadSentEmails}
          disabled={emailsLoading}
          className="w-full py-12 border-2 border-dashed border-slate-700 rounded-xl text-slate-400 hover:border-slate-500 hover:text-white transition-colors"
        >
          <Mail size={40} className="mx-auto mb-3" />
          <p className="font-medium">Click to load sent emails</p>
          <p className="text-sm mt-1">View all emails sent to clients with their details</p>
        </button>
      ) : (
        <div className="bg-card-bg rounded-xl border border-card-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-card-border">
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-400">Client</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-400">Subject Line</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-400">Email Type</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-400">Sent Date</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {sentEmails.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-500">No sent emails found</td>
                  </tr>
                ) : (
                  sentEmails.map((lead, i) => {
                    const step = lead.sequence_step
                    const template = EMAIL_TEMPLATES[step] || EMAIL_TEMPLATES[1]
                    return (
                      <tr key={i} className="border-b border-card-border hover:bg-slate-800/50 transition-colors">
                        <td className="px-4 py-4">
                          <div>
                            <p className="text-sm font-medium text-white">{lead.name}</p>
                            <p className="text-xs text-slate-500">{lead.company}</p>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm text-slate-300 max-w-xs truncate">
                          {lead.subject_line || 'No subject'}
                        </td>
                        <td className="px-4 py-4">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${template.color}`}>
                            {template.label}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-sm text-slate-400">
                          {lead.email_sent_at_raw || lead.email_sent_at || 'N/A'}
                        </td>
                        <td className="px-4 py-4">
                          {lead.replied ? (
                            <span className="text-green-400 text-sm flex items-center gap-1">
                              <span className="w-2 h-2 bg-green-400 rounded-full" />
                              Replied
                            </span>
                          ) : lead.opt_out ? (
                            <span className="text-red-400 text-sm flex items-center gap-1">
                              <span className="w-2 h-2 bg-red-400 rounded-full" />
                              Opted out
                            </span>
                          ) : (
                            <span className="text-slate-500 text-sm flex items-center gap-1">
                              <span className="w-2 h-2 bg-slate-500 rounded-full" />
                              No reply
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className="p-3 border-t border-card-border text-xs text-slate-500 text-right">
            {sentEmails.length} emails sent
          </div>
        </div>
      )}

      {/* Subject Line Performance Ranking */}
      <div className="pt-4">
        <h2 className="text-xl font-bold text-white">Subject Line Performance</h2>
        <p className="text-slate-400 mt-1">Ranked by reply rate</p>
      </div>

      {subjects.length === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No subject line data yet"
          description="Subject line performance will appear here once emails have been sent and replies start coming in."
        />
      ) : (
        <div className="space-y-4">
          {subjects.map((s, i) => (
            <div key={s.subject || i} className="bg-card-bg rounded-xl border border-card-border p-6 flex items-center gap-6">
              <div className="w-12 h-12 bg-blue-600/20 rounded-full flex items-center justify-center">
                <span className="text-lg font-bold text-blue-400">#{i + 1}</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-white">{s.subject}</h3>
                <p className="text-sm text-slate-400 mt-1">{s.replies} replies</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-green-400">{s.rate != null ? s.rate.toFixed(1) : '0.0'}%</p>
                <p className="text-xs text-slate-500">reply rate</p>
              </div>
              <div className="w-32">
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full transition-all"
                    style={{ width: `${Math.min(s.rate ?? 0, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
