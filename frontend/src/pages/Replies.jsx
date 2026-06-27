import { useState } from 'react'
import { useReplies } from '../hooks/usePolling'
import { MessageSquare, UserCheck, UserX, RefreshCw, Mail } from 'lucide-react'
import KPICard from '../components/KPICard'
import EmptyState from '../components/EmptyState'
import { SkeletonPage } from '../components/Skeleton'

export default function Replies() {
  const { data, loading, lastUpdated, refresh } = useReplies()
  const [filter, setFilter] = useState('all')

  if (loading) return <SkeletonPage />
  if (!data) return <div className="text-red-400">Failed to load replies</div>

  const filtered = data.replies.filter(r => {
    if (filter === 'positive') return !r.opt_out
    if (filter === 'unsubscribed') return r.opt_out
    return true
  })

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Email Replies</h1>
          <p className="text-slate-400 mt-1">
            Track and manage incoming replies
            {lastUpdated && (
              <span className="text-xs text-slate-500 ml-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg transition-colors text-sm"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KPICard label="Total Replies" value={data.total} icon={MessageSquare} color="blue" />
        <KPICard label="Positive Replies" value={data.positive} icon={UserCheck} color="green" />
        <KPICard label="Unsubscribed" value={data.unsubscribed} icon={UserX} color="red" />
      </div>

      <div className="flex gap-4">
        {['all', 'positive', 'unsubscribed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {filtered.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="No replies yet"
            description="Replies from your leads will appear here once they start responding to your emails."
          />
        ) : (
          filtered.map((reply, i) => {
            const content = reply.reply_snippet || ''

            return (
              <div key={reply.lead_id || reply.email || i} className="bg-card-bg rounded-xl border border-card-border p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-white">{reply.name}</h3>
                    <p className="text-sm text-slate-400">{reply.email}</p>
                    <p className="text-sm text-slate-500">{reply.company}</p>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    reply.opt_out
                      ? 'bg-red-500/20 text-red-400'
                      : 'bg-green-500/20 text-green-400'
                  }`}>
                    {reply.opt_out ? 'Unsubscribed' : 'Positive'}
                  </span>
                </div>

                {reply.subject_line && (
                  <div className="mt-3 flex items-center gap-2 text-sm text-blue-400">
                    <Mail size={14} />
                    <span>{reply.subject_line}</span>
                  </div>
                )}

                {content && (
                  <div className="mt-3 p-3 bg-slate-800 rounded-lg">
                    <p className="text-sm text-slate-300">{content}</p>
                  </div>
                )}

                <div className="mt-3 flex gap-4 text-xs text-slate-500">
                  <span>Sent: {reply.email_sent_at || 'N/A'}</span>
                  <span>Step: {reply.sequence_step}</span>
                  <span>Tier: {reply.tier || 'N/A'}</span>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
