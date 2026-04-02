'use client'

import { useEffect, useState } from 'react'

export default function Reports() {
  const [experiments, setExperiments] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)

  const downloadBenchmarkCSV = async () => {
    const res = await fetch('http://localhost:8000/api/experiments')
    const data = await res.json()
    const csv = [
      ['Experiment ID', 'Scenario', 'Engine', 'Proposed Accuracy', 'Composite Score', 'Sector Compliance'],
      ...data.map((e: any) => [
        e.id,
        e.scenario,
        e.engine || 'python',
        ((e.proposed_accuracy || 0) * 100).toFixed(1) + '%',
        ((e.proposed_composite_score || 0) * 100).toFixed(1) + '%',
        ((e.proposed_sector_compliance || 0) * 100).toFixed(1) + '%',
      ])
    ].map(row => row.join(',')).join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'engine_benchmark_summary.csv'
    a.click()
  }

  useEffect(() => {
    Promise.all([
      fetch('http://localhost:8000/api/experiments').then(res => res.json()),
      fetch('http://localhost:8000/api/dashboard/stats').then(res => res.json())
    ]).then(([exps, stats]) => {
      setExperiments(exps)
      setStats(stats)
    })
  }, [])

  const downloadCSV = () => {
    const csv = [
      ['Experiment ID', 'Scenario', 'Baseline Accuracy', 'Proposed Accuracy', 'Improvement', 'Proposed Composite Score', 'Proposed Sector Compliance'],
      ...experiments.map(e => [
        e.id,
        e.scenario,
        (e.baseline_accuracy * 100).toFixed(1) + '%',
        (e.proposed_accuracy * 100).toFixed(1) + '%',
        ((e.proposed_accuracy - e.baseline_accuracy) * 100).toFixed(1) + '%',
        ((e.proposed_composite_score || 0) * 100).toFixed(1) + '%',
        ((e.proposed_sector_compliance || 0) * 100).toFixed(1) + '%'
      ])
    ].map(row => row.join(',')).join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'experiment_results.csv'
    a.click()
  }

  const downloadJSON = () => {
    const json = JSON.stringify({
      summary: stats,
      experiments: experiments
    }, null, 2)
    
    const blob = new Blob([json], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'experiment_results.json'
    a.click()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Reports & Export</h1>
        <p className="text-gray-600 mt-2">Generate and export experiment reports</p>
      </div>

      {/* Summary */}
      {stats && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Experiment Summary</h2>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-600">Total Experiments</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_experiments}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Baseline Detection Rate</p>
              <p className="text-2xl font-bold text-orange-600">{(stats.baseline_detection_rate * 100).toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Proposed Detection Rate</p>
              <p className="text-2xl font-bold text-green-600">{(stats.proposed_detection_rate * 100).toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Avg Improvement</p>
              <p className="text-2xl font-bold text-blue-600">
                {((stats.proposed_detection_rate - stats.baseline_detection_rate) * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Avg Overhead</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.average_overhead_ms.toFixed(0)}ms</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Avg Composite Score</p>
              <p className="text-2xl font-bold text-emerald-700">
                {(experiments.length > 0
                  ? (experiments.reduce((acc, e) => acc + (e.proposed_composite_score || 0), 0) / experiments.length) * 100
                  : 0
                ).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Export Options */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Export Data</h2>
        <div className="space-y-3">
          <button
            onClick={downloadCSV}
            className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 text-left flex items-center"
          >
            <span className="mr-3">📊</span>
            <div>
              <p className="font-semibold">Download as CSV</p>
              <p className="text-xs text-blue-100">Experiment results in spreadsheet format</p>
            </div>
          </button>
          <button
            onClick={downloadJSON}
            className="w-full bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 text-left flex items-center"
          >
            <span className="mr-3">{ '{}'}</span>
            <div>
              <p className="font-semibold">Download as JSON</p>
              <p className="text-xs text-green-100">Structured data for further analysis</p>
            </div>
          </button>
          <button
            onClick={downloadBenchmarkCSV}
            className="w-full bg-violet-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-violet-700 text-left flex items-center"
          >
            <span className="mr-3">⚙️</span>
            <div>
              <p className="font-semibold">Download Engine Benchmark CSV</p>
              <p className="text-xs text-violet-100">Python vs Spark comparison summary for experiment runs</p>
            </div>
          </button>
        </div>
      </div>

      {/* Thesis Summary */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Thesis Summary</h2>
        <div className="space-y-3 text-sm text-gray-700">
          <p>✓ <strong>Proposed pipeline improves detection accuracy by {((stats?.proposed_detection_rate - stats?.baseline_detection_rate) * 100).toFixed(1)}%</strong></p>
          <p>✓ <strong>Reduces false negatives by {stats?.baseline_false_negatives - stats?.proposed_false_negatives} on average</strong></p>
          <p>✓ Adds systematic stage-level validations for comprehensive integrity checking</p>
          <p>⚠ Trade-off: Increases latency overhead ({stats?.average_overhead_ms.toFixed(0)}ms per run)</p>
          <p>✓ Suitable for mission-critical data pipelines where data integrity is paramount</p>
        </div>
      </div>
    </div>
  )
}