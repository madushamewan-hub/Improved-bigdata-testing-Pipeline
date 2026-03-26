'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

interface DashboardStats {
  total_experiments: number
  baseline_detection_rate: number
  proposed_detection_rate: number
  baseline_false_negatives: number
  proposed_false_negatives: number
  average_overhead_ms: number
}

const KPI_EXPLANATIONS: Record<string, string> = {
  total_experiments: 'Number of completed pipeline experiments used to produce the dashboard metrics.',
  baseline_detection_rate: 'Baseline pipeline % of known data issues detected successfully.',
  proposed_detection_rate: 'Proposed pipeline % of known data issues detected successfully.',
  baseline_false_negatives: 'Average count of true positives missed by the baseline pipeline.',
  proposed_false_negatives: 'Average count of true positives missed by the proposed pipeline.',
  average_overhead_ms: 'Average additional time in milliseconds introduced by the proposed pipeline over baseline.',
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [backendLive, setBackendLive] = useState<boolean | null>(null)
  const [backendError, setBackendError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(res => {
        if (!res.ok) throw new Error(`Health API failed: ${res.status}`)
        return res.json()
      })
      .then(data => {
        if (data?.status === 'ok') {
          setBackendLive(true)
          setBackendError(null)
        } else {
          setBackendLive(false)
          setBackendError('Backend health check failed')
        }
      })
      .catch(err => {
        console.error('Backend health error:', err)
        setBackendLive(false)
        setBackendError(err.message || 'Unable to reach backend')
      })

    fetch('http://localhost:8000/api/dashboard/stats')
      .then(res => {
        if (!res.ok) throw new Error(`Stats API failed: ${res.status}`)
        return res.json()
      })
      .then(data => {
        setStats(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Error loading stats:', err)
        setLoading(false)
      })
  }, [])

  const KPICard = ({ title, value, subtitle, color, metricKey }: any) => {
    const explanation = metricKey ? KPI_EXPLANATIONS[metricKey] : ''
    return (
      <div className={`${color} rounded-lg shadow p-6 text-white`}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium opacity-90">{title}</p>
          {explanation && (
            <span
              className="text-xs px-2 py-1 bg-white/20 rounded-full cursor-help"
              title={explanation}
              aria-label={explanation}
            >
              ℹ️
            </span>
          )}
        </div>
        <p className="text-3xl font-bold mt-2">{typeof value === 'number' ? value.toFixed(2) : value}</p>
        {subtitle && <p className="text-xs opacity-75 mt-1">{subtitle}</p>}
        {/* For screen readers and longer references we can keep the details visible */}
        {metricKey && KPI_EXPLANATIONS[metricKey] && (
          <p className="text-[10px] opacity-80 mt-2 bg-white/10 rounded px-2 py-1">{KPI_EXPLANATIONS[metricKey]}</p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-6">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">Integrity Testing Dashboard</h1>
          <p className="text-gray-600 mt-2">Compare baseline vs. integrity-focused data pipeline performance</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-xs font-bold ${backendLive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            Backend: {backendLive ? 'Live' : backendLive === false ? 'Down' : 'Checking...'}
          </span>
          {backendError && <span className="text-xs text-red-600">{backendError}</span>}
        </div>
      </div>

      {loading ? (
        <div className="text-center text-gray-500">Loading dashboard statistics...</div>
      ) : stats ? (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <KPICard 
              title="Total Experiments Run"
              value={stats.total_experiments}
              metricKey="total_experiments"
              color="bg-blue-600"
            />
            <div className="lg:col-span-2 space-y-4">
              <div className="text-sm font-semibold text-gray-700">Baseline Pipeline Metrics</div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <KPICard 
                  title="Detection Rate"
                  value={`${(stats.baseline_detection_rate * 100).toFixed(1)}%`}
                  metricKey="baseline_detection_rate"
                  color="bg-orange-600"
                />
                <KPICard 
                  title="False Negatives"
                  value={stats.baseline_false_negatives}
                  metricKey="baseline_false_negatives"
                  color="bg-red-600"
                />
                <KPICard 
                  title="Avg Latency"
                  value="N/A"
                  subtitle="Baseline baseline for comparison"
                  color="bg-orange-400"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-start-2 text-sm font-semibold text-gray-700">Proposed Pipeline Metrics</div>
            <div />
            <div />
            <div className="lg:col-span-2">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <KPICard 
                  title="Detection Rate"
                  value={`${(stats.proposed_detection_rate * 100).toFixed(1)}%`}
                  metricKey="proposed_detection_rate"
                  color="bg-green-600"
                />
                <KPICard 
                  title="False Negatives"
                  value={stats.proposed_false_negatives}
                  metricKey="proposed_false_negatives"
                  color="bg-yellow-600"
                />
                <KPICard 
                  title="Latency Overhead"
                  value={`${stats.average_overhead_ms.toFixed(0)}ms`}
                  metricKey="average_overhead_ms"
                  subtitle="vs baseline" 
                  color="bg-purple-600"
                />
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Link href="/dashboard/upload" className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition text-center">
                <p className="text-2xl mb-2">📤</p>
                <p className="font-semibold text-gray-900">Upload Data</p>
                <p className="text-xs text-gray-500 mt-1">Upload custom dataset</p>
              </Link>
              <Link href="/dashboard/flows" className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition text-center">
                <p className="text-2xl mb-2">⚙️</p>
                <p className="font-semibold text-gray-900">View Flows</p>
                <p className="text-xs text-gray-500 mt-1">Compare pipeline architectures</p>
              </Link>
              <Link href="/dashboard/experiments" className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition text-center">
                <p className="text-2xl mb-2">🧪</p>
                <p className="font-semibold text-gray-900">Run Experiment</p>
                <p className="text-xs text-gray-500 mt-1">Execute pipeline test</p>
              </Link>
              <Link href="/dashboard/results" className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition text-center">
                <p className="text-2xl mb-2">📈</p>
                <p className="font-semibold text-gray-900">View Results</p>
                <p className="text-xs text-gray-500 mt-1">Compare metrics</p>
              </Link>
            </div>
          </div>

          {/* Summary */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Performance Summary</h2>
            <div className="space-y-2 text-gray-700">
              <p>✓ Proposed pipeline shows <span className="font-bold text-green-600">{((stats.proposed_detection_rate - stats.baseline_detection_rate) * 100).toFixed(1)}%</span> improvement in detection rate</p>
              <p>✓ Reduced false negatives by <span className="font-bold text-green-600">{stats.baseline_false_negatives - stats.proposed_false_negatives}</span> on average</p>
              <p>⚠ Latency overhead: <span className="font-bold text-yellow-600">{stats.average_overhead_ms.toFixed(0)}ms</span> per pipeline run</p>
            </div>
          </div>
        </>
      ) : (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          No experiments yet. Upload data and run an experiment to get started.
        </div>
      )}
    </div>
  )
}