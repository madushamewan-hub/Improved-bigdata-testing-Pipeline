'use client'

import { useEffect, useState } from 'react'

export default function StageChecks() {
  const [experiments, setExperiments] = useState<any[]>([])
  const [selectedExp, setSelectedExp] = useState<number | null>(null)
  const [checks, setChecks] = useState<any>(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/experiments')
      .then(res => res.json())
      .then(setExperiments)
      .catch(console.error)
  }, [])

  useEffect(() => {
    if (selectedExp) {
      fetch(`http://localhost:8000/api/stage-checks/${selectedExp}`)
        .then(res => res.json())
        .then(setChecks)
        .catch(console.error)
    }
  }, [selectedExp])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Stage-Level Validation Checks</h1>
        <p className="text-gray-600 mt-2">View detailed checks performed at each pipeline stage</p>
      </div>

      {experiments.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No experiments found. Run an experiment first to view stage checks.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Experiment List */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Select Experiment</h2>
            <div className="space-y-2">
              {experiments.map((exp, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedExp(exp.id)}
                  className={`w-full text-left px-4 py-3 rounded text-sm ${
                    selectedExp === exp.id ? 'bg-blue-100 border border-blue-600' : 'hover:bg-gray-100 border border-gray-200'
                  }`}
                >
                  <p className="font-semibold">{exp.scenario}</p>
                  <p className="text-xs text-gray-500">ID: {exp.id}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Checks Table */}
          {checks && (
            <div className="lg:col-span-2 space-y-6">
              {/* Baseline Checks */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Baseline Checks</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="px-4 py-2 text-left">Stage</th>
                        <th className="px-4 py-2 text-left">Check</th>
                        <th className="px-4 py-2 text-left">Status</th>
                        <th className="px-4 py-2 text-left">Findings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {checks.baseline.map((c: any, i: number) => (
                        <tr key={i} className="border-t">
                          <td className="px-4 py-2">{c.stage}</td>
                          <td className="px-4 py-2">{c.check}</td>
                          <td className="px-4 py-2">{c.passed ? '✓ Pass' : '✗ Fail'}</td>
                          <td className="px-4 py-2">{c.findings}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Proposed Checks */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Proposed Checks</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="px-4 py-2 text-left">Stage</th>
                        <th className="px-4 py-2 text-left">Check</th>
                        <th className="px-4 py-2 text-left">Status</th>
                        <th className="px-4 py-2 text-left">Findings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {checks.proposed.map((c: any, i: number) => (
                        <tr key={i} className="border-t">
                          <td className="px-4 py-2">{c.stage}</td>
                          <td className="px-4 py-2">{c.check}</td>
                          <td className="px-4 py-2">{c.passed ? '✓ Pass' : '✗ Fail'}</td>
                          <td className="px-4 py-2">{c.findings}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}