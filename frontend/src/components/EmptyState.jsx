import { Inbox } from 'lucide-react'

export default function EmptyState({ icon: Icon = Inbox, title = 'No data found', description = '', action, actionLabel = '', onAction }) {
  return (
    <div className="bg-card-bg rounded-xl border border-card-border p-12 text-center">
      <Icon size={48} className="mx-auto mb-4 text-slate-600" />
      <h3 className="text-lg font-semibold text-slate-300 mb-1">{title}</h3>
      {description && <p className="text-sm text-slate-500 mb-6 max-w-md mx-auto">{description}</p>}
      {action && (
        <button
          onClick={onAction}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}