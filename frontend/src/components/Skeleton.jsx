export function SkeletonCard() {
  return (
    <div className="bg-card-bg rounded-xl border border-card-border p-6 animate-pulse">
      <div className="h-4 bg-slate-700 rounded w-1/3 mb-3" />
      <div className="h-8 bg-slate-700 rounded w-1/4" />
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 6 }) {
  return (
    <div className="bg-card-bg rounded-xl border border-card-border overflow-hidden animate-pulse">
      <div className="border-b border-card-border p-4">
        <div className="flex gap-6">
          {Array.from({ length: cols }).map((_, i) => (
            <div key={i} className="h-4 bg-slate-700 rounded flex-1" />
          ))}
        </div>
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="border-b border-card-border p-4">
          <div className="flex gap-6">
            {Array.from({ length: cols }).map((_, j) => (
              <div key={j} className="h-4 bg-slate-700 rounded flex-1" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="bg-card-bg rounded-xl border border-card-border p-6 animate-pulse">
      <div className="h-4 bg-slate-700 rounded w-1/4 mb-6" />
      <div className="h-64 bg-slate-700/50 rounded" />
    </div>
  )
}

export function SkeletonPage() {
  return (
    <div className="space-y-6">
      <div className="h-8 bg-slate-700 rounded w-1/4 animate-pulse mb-2" />
      <div className="h-4 bg-slate-700 rounded w-1/2 animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mt-6">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SkeletonChart />
        <SkeletonChart />
      </div>
    </div>
  )
}