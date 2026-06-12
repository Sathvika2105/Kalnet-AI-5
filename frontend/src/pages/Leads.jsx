import { useState } from 'react'
import { useLeads } from '../hooks/usePolling'
import DataTable from '../components/DataTable'
import BulkUploadModal from '../components/BulkUploadModal'
import { RefreshCw, Upload } from 'lucide-react'

export default function Leads() {
  const [filters, setFilters] = useState({ replied: '', opt_out: '', step: '' })
  const [showUpload, setShowUpload] = useState(false)
  const { data, loading, lastUpdated, refresh } = useLeads(filters)

  const leads = data?.leads || []

  const columns = [
    { key: 'lead_id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'Email' },
    { key: 'company', label: 'Company' },
    { key: 'email_sent_at', label: 'Sent At' },
    { key: 'sequence_step', label: 'Step' },
    {
      key: 'replied',
      label: 'Replied',
      render: (v) => (
        <span className={v ? 'text-green-400' : 'text-slate-500'}>
          {v ? 'Yes' : 'No'}
        </span>
      )
    },
    { key: 'tier', label: 'Tier' },
    { key: 'subject_line', label: 'Subject' },
    {
      key: 'opt_out',
      label: 'Opt-out',
      render: (v) => (
        <span className={v ? 'text-red-400' : 'text-slate-500'}>
          {v ? 'Yes' : 'No'}
        </span>
      )
    },
  ]

  if (loading) return <div className="text-slate-400">Loading...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Leads Database</h1>
          <p className="text-slate-400 mt-1">
            {leads.length} total leads
            {lastUpdated && (
              <span className="text-xs text-slate-500 ml-2">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors text-sm"
          >
            <Upload size={16} />
            Bulk Upload
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

      <BulkUploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onSuccess={refresh}
      />

      <div className="flex gap-4">
        <select
          value={filters.replied}
          onChange={(e) => setFilters({ ...filters, replied: e.target.value })}
          className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm"
        >
          <option value="">All Replies</option>
          <option value="true">Replied</option>
          <option value="false">Not Replied</option>
        </select>

        <select
          value={filters.opt_out}
          onChange={(e) => setFilters({ ...filters, opt_out: e.target.value })}
          className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm"
        >
          <option value="false">Active</option>
          <option value="true">Opted Out</option>
        </select>

        <select
          value={filters.step}
          onChange={(e) => setFilters({ ...filters, step: e.target.value })}
          className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm"
        >
          <option value="">All Steps</option>
          <option value="1">Step 1</option>
          <option value="2">Step 2</option>
          <option value="3">Step 3</option>
        </select>
      </div>

      <DataTable columns={columns} data={leads} pageSize={15} />
    </div>
  )
}
