'use client'

import { useEffect, useState } from 'react'

export default function DBView() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('http://localhost:8000/api/db-summary')
      .then((res) => {
        if (!res.ok) throw new Error(`DB Summary failed: ${res.status}`)
        return res.json()
      })
      .then((json) => {
        setData(json)
        setLoading(false)
      })
      .catch((err) => {
        console.error('DB summary error:', err)
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return <div className="text-center text-gray-500">Loading DB view...</div>
  }

  if (error) {
    return <div className="text-center text-red-500">{error}</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Database View</h1>
      <p className="text-gray-600">View datasets, experiments, pipeline results, and stage checks.</p>

      {['datasets', 'experiment_runs', 'pipeline_results', 'stage_checks'].map((section) => (
        <div key={section} className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-3 capitalize">{section.replace('_', ' ')}</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-100">
                <tr>
                  {data[section] && data[section].length > 0
                    ? Object.keys(data[section][0]).map((col) => (
                        <th key={col} className="px-2 py-1 text-left font-medium text-gray-700">
                          {col}
                        </th>
                      ))
                    : <th className="px-2 py-1 text-left text-gray-500">No data</th>}
                </tr>
              </thead>
              <tbody>
                {data[section] && data[section].length > 0 ? (
                  data[section].map((row: any, i: number) => (
                    <tr key={i} className="border-t">
                      {Object.values(row).map((val: any, j: number) => (
                        <td key={j} className="px-2 py-1 break-words max-w-xs">{String(val)}</td>
                      ))}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={20} className="px-2 py-3 text-gray-500">No records</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}
