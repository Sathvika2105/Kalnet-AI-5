import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function KPICard({ label, value, icon: Icon, trend, color = 'blue' }) {
  const colors = {
    blue: 'from-blue-600 to-blue-700',
    green: 'from-green-600 to-green-700',
    purple: 'from-purple-600 to-purple-700',
    orange: 'from-orange-600 to-orange-700',
    red: 'from-red-600 to-red-700',
  }

  const TrendIcon = trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus
  const trendColor = trend > 0 ? 'text-green-400' : trend < 0 ? 'text-red-400' : 'text-slate-400'

  return (
    <div className={`bg-gradient-to-br ${colors[color]} rounded-xl p-5 shadow-lg`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-white/70">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
          {trend !== undefined && (
            <div className={`flex items-center gap-1 mt-2 ${trendColor}`}>
              <TrendIcon size={14} />
              <span className="text-sm">{Math.abs(trend)}%</span>
            </div>
          )}
        </div>
        {Icon && (
          <div className="w-12 h-12 bg-white/10 rounded-lg flex items-center justify-center">
            <Icon size={24} className="text-white/80" />
          </div>
        )}
      </div>
    </div>
  )
}
