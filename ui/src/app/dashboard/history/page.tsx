'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function History() {
  const [experiments, setExperiments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('http://localhost:8000/api/experiments')
      .then(res => res.json())
      .then(data => {
        setExperiments(data)
        setLoading(false)
      })
      .catch(console.error)
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Experiment History</h1>
        <p className="text-gray-600 mt-2">All experiments run in this session</p>
      </div>

      {loading ? (
        <div className="text-center text-gray-500">Loading history...</div>
      ) : experiments.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No experiment history yet.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600">ID</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600">Scenario</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600">Baseline Accuracy</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600">Proposed Accuracy</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600">Timestamp</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {experiments.map((exp) => (
                <tr key={exp.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900">#{exp.id}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">{exp.scenario}</td>
                  <td className="px-6 py-4 text-sm">
                    <span className="bg-orange-100 text-orange-800 px-2 py-1 rounded text-xs font-semibold">
                      {(exp.baseline_accuracy * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-semibold">
                      {(exp.proposed_accuracy * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {new Date(exp.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <Link href={`/dashboard/results`} className="text-blue-600 hover:underline">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}