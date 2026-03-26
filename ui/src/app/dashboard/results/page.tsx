'use client'

import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'

interface ExperimentSummary {
  id: number
  dataset_id: number
  scenario: string
  baseline_accuracy: number
  proposed_accuracy: number
  timestamp: string
}

export default function Results() {
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([])
  const [selectedExp, setSelectedExp] = useState<number | null>(null)
  const [expDetails, setExpDetails] = useState<any>(null)
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

  useEffect(() => {
    if (selectedExp) {
      fetch(`http://localhost:8000/api/experiments/${selectedExp}`)
        .then(res => res.json())
        .then(setExpDetails)
        .catch(console.error)
    }
  }, [selectedExp])

  if (loading) return <div className="text-center text-gray-500">Loading experiments...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Results Comparison</h1>
        <p className="text-gray-600 mt-2">View and analyze experiment outcomes</p>
      </div>

      {experiments.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No experiments yet. <a href="/dashboard/experiments" className="text-blue-600">Run an experiment</a> first.
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-6">
          {/* Chart */}
          <div className="col-span-2 bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Accuracy Comparison</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={experiments}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="scenario" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="baseline_accuracy" fill="#f97316" name="Baseline" />
                <Bar dataKey="proposed_accuracy" fill="#16a34a" name="Proposed" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Experiment List */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Experiments</h2>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {experiments.map(exp => (
                <button
                  key={exp.id}
                  onClick={() => setSelectedExp(exp.id)}
                  className={`w-full text-left px-4 py-3 rounded ${
                    selectedExp === exp.id
                      ? 'bg-blue-100 border border-blue-600'
                      : 'hover:bg-gray-100 border border-gray-200'
                  }`}
                >
                  <p className="text-sm font-semibold text-gray-900">{exp.scenario}</p>
                  <p className="text-xs text-gray-500">ID: {exp.id}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Detailed Results */}
      {expDetails && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Baseline */}
          {expDetails.baseline && (
            <div className="bg-orange-50 rounded-lg shadow p-6 border border-orange-200">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Baseline Results</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Accuracy:</span>
                  <span className="font-bold text-orange-600">{(expDetails.baseline.accuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Precision:</span>
                  <span className="font-bold">{expDetails.baseline.precision.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Recall:</span>
                  <span className="font-bold">{expDetails.baseline.recall.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">False Positives:</span>
                  <span className="font-bold">{expDetails.baseline.false_positives}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">False Negatives:</span>
                  <span className="font-bold text-red-600">{expDetails.baseline.false_negatives}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Latency:</span>
                  <span className="font-bold">{expDetails.baseline.latency.toFixed(0)}ms</span>
                </div>
              </div>
            </div>
          )}

          {/* Proposed */}
          {expDetails.proposed && (
            <div className="bg-green-50 rounded-lg shadow p-6 border border-green-200">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Proposed Results</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Accuracy:</span>
                  <span className="font-bold text-green-600">{(expDetails.proposed.accuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Precision:</span>
                  <span className="font-bold">{expDetails.proposed.precision.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Recall:</span>
                  <span className="font-bold">{expDetails.proposed.recall.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">False Positives:</span>
                  <span className="font-bold">{expDetails.proposed.false_positives}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">False Negatives:</span>
                  <span className="font-bold text-red-600">{expDetails.proposed.false_negatives}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Latency:</span>
                  <span className="font-bold">{expDetails.proposed.latency.toFixed(0)}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Overhead:</span>
                  <span className="font-bold text-yellow-600">+{expDetails.proposed.overhead.toFixed(0)}ms</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}