import { useState } from 'react'
import { useMetrics } from '../hooks/usePolling'
import KPICard from '../components/KPICard'
import { Users, Send, MessageSquare, TrendingUp, UserX, RefreshCw, Play } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import api from '../api/client'

const COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444']

export default function Overview() {
  const { data: metrics, loading, lastUpdated, refresh } = useMetrics()
  const [running, setRunning] = useState(false)
  const [pipelineMsg, setPipelineMsg] = useState('')

  const runPipeline = async () => {
    setRunning(true)
    setPipelineMsg('')
    try {
      const res = await api.post('/pipeline/run')
      setPipelineMsg('✅ ' + res.data.message)
      setTimeout(refresh, 5000)
    } catch (e) {
      setPipelineMsg('❌ Failed to trigger pipeline')
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <div className="text-slate-400">Loading...</div>
  if (!metrics) return <div className="text-red-400">Failed to load metrics</div>

  const tierData = Object.entries(metrics.tier_breakdown || {}).map(([tier, count]) => ({
    name: `Tier ${tier}`,
    value: count,
  }))

  const funnelData = [
    { name: 'Total Leads', value: metrics.total_leads },
    { name: 'Emails Sent', value: metrics.emails_sent },
    { name: 'Replies', value: metrics.total_replies },
    { name: 'Opt-outs', value: metrics.opt_outs },
  ]

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard Overview</h1>
          <p className="text-slate-400 mt-1">
            Real-time email automation metrics
            {lastUpdated && (
              <span className="text-xs text-slate-500 ml-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {pipelineMsg && (
            <span className="text-sm text-slate-400">{pipelineMsg}</span>
          )}
          <button
            onClick={runPipeline}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg transition-colors text-sm"
          >
            <Play size={16} />
            {running ? 'Running...' : 'Run Pipeline'}
          </button>
          <button
            onClick={refresh}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg transition-colors text-sm"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard label="Total Leads" value={metrics.total_leads} icon={Users} color="blue" />
        <KPICard label="Emails Sent" value={metrics.emails_sent} icon={Send} color="green" />
        <KPICard label="Replies" value={metrics.total_replies} icon={MessageSquare} color="purple" />
        <KPICard label="Reply Rate" value={`${metrics.reply_rate}%`} icon={TrendingUp} color="orange" />
        <KPICard label="Opt-outs" value={metrics.opt_outs} icon={UserX} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Email Funnel</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={funnelData}>
              <XAxis dataKey="name" tick={{ fill: '#94a3b8' }} />
              <YAxis tick={{ fill: '#94a3b8' }} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card-bg rounded-xl border border-card-border p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Tier Breakdown</h3>
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
            <p className="text-slate-400 text-center py-10">No tier data available</p>
          )}
        </div>
      </div>

      <div className="bg-card-bg rounded-xl border border-card-border p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Pending Actions</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-sm text-slate-400">Leads awaiting first email</p>
            <p className="text-2xl font-bold text-yellow-400 mt-1">{metrics.pending}</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-sm text-slate-400">Opted out (do not contact)</p>
            <p className="text-2xl font-bold text-red-400 mt-1">{metrics.opt_outs}</p>
          </div>
        </div>
      </div>
    </div>
  )
}