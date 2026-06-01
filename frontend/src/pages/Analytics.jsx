import { useAnalytics } from '../hooks/usePolling'
import { RefreshCw } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

const COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444']

export default function Analytics() {
  const { data, loading, lastUpdated, refresh } = useAnalytics()

  if (loading) return <div className="text-slate-400">Loading...</div>
  if (!data) return <div className="text-red-400">Failed to load analytics</div>

  const { overview, sequence_steps } = data

  const tierData = Object.entries(overview.tier_breakdown || {}).map(([tier, count]) => ({
    name: `Tier ${tier}`,
    value: count,
  }))

  const stepData = Object.entries(sequence_steps || {}).map(([step, count]) => ({
    name: `Step ${step}`,
    value: count,
  }))

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-slate-400 mt-1">
            Detailed email performance metrics
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
        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <p className="text-sm text-slate-400">Total Sent</p>
          <p className="text-3xl font-bold text-white mt-1">{overview.total_sent}</p>
        </div>
        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <p className="text-sm text-slate-400">Total Replies</p>
          <p className="text-3xl font-bold text-white mt-1">{overview.total_replies}</p>
        </div>
        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <p className="text-sm text-slate-400">Reply Rate</p>
          <p className="text-3xl font-bold text-blue-400 mt-1">{overview.reply_rate}%</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Emails by Sequence Step</h3>
          {stepData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={stepData}>
                <XAxis dataKey="name" tick={{ fill: '#94a3b8' }} />
                <YAxis tick={{ fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
                <Bar dataKey="value" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-400 text-center py-10">No data</p>
          )}
        </div>

        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Tier Distribution</h3>
          {tierData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={tierData} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {tierData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-400 text-center py-10">No tier data</p>
          )}
        </div>
      </div>
    </div>
  )
}
