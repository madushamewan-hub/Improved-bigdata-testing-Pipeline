'use client'

import { useEffect, useState } from 'react'

interface Dataset {
  id: number
  name: string
  row_count: number
}

const SCENARIOS = ['real_world', 'clean', 'duplicated', 'dropped', 'corrupted', 'schema_drift', 'out_of_order', 'mixed']

const SCENARIO_DESCRIPTIONS: Record<string, { title: string; description: string; useCase: string }> = {
  real_world: {
    title: '🌍 Real-World Data (No Injection)',
    description: 'Use your actual uploaded dataset as-is with no synthetic issues injected. Perfect for production validation.',
    useCase: 'Validate both pipelines against real data; establish production baseline and measure true overhead.'
  },
  clean: {
    title: 'Clean Data (Synthetic)',
    description: 'Synthetically generated clean data with no quality issues. All rows are valid and complete.',
    useCase: 'Baseline test to verify pipeline stability under ideal conditions.'
  },
  duplicated: {
    title: 'Duplicated Rows',
    description: '20% of rows are duplicated. Tests ability to detect and handle repeated records.',
    useCase: 'Verify deduplication logic and duplicate detection accuracy.'
  },
  dropped: {
    title: 'Missing/Dropped Data',
    description: '20% of rows contain missing values. Tests handling of incomplete records.',
    useCase: 'Ensure pipeline detects data loss and null value handling.'
  },
  corrupted: {
    title: 'Data Corruption',
    description: '20% of rows have corrupted/invalid values. Tests data validation.',
    useCase: 'Validate type checking and corruption detection in pipeline.'
  },
  schema_drift: {
    title: 'Schema Drift',
    description: 'Data columns change type or structure during processing.',
    useCase: 'Test schema validation and downstream incompatibility detection.'
  },
  out_of_order: {
    title: 'Out of Order',
    description: '20% of rows arrive in incorrect sequence. Tests ordering assumptions.',
    useCase: 'Verify handling of unordered/scrambled data streams.'
  },
  mixed: {
    title: 'Mixed Issues',
    description: 'Combination of all issues (~10% each). Real-world complexity.',
    useCase: 'Comprehensive test with multiple simultaneous data quality issues.'
  }
}

const MODE_DESCRIPTIONS: Record<string, { title: string; description: string; behavior: string[] }> = {
  baseline: {
    title: 'Baseline Mode',
    description: 'Runs the minimal pipeline with basic checks only.',
    behavior: [
      'Only basic schema detection',
      'Simple type conversion',
      'Manual review stage',
      'Lower latency (~50-100ms)'
    ]
  },
  proposed: {
    title: 'Proposed Mode',
    description: 'Runs the integrity-focused pipeline with all checks.',
    behavior: [
      'Schema validation + null checks',
      'Duplicate detection + checksums',
      'Transformation assertion checks',
      'Row count verification + reconciliation',
      'Higher accuracy but higher latency (~200-400ms)'
    ]
  },
  compare: {
    title: 'Compare Mode',
    description: 'Runs both baseline and proposed, then compares results side-by-side.',
    behavior: [
      'Executes both pipelines',
      'Shows accuracy improvement',
      'Displays latency overhead',
      'Best for evaluation and decision-making'
    ]
  }
}

const METRIC_EXPLANATIONS: Record<string, { name: string; definition: string; interpretation: string; goodRange: string }> = {
  accuracy: {
    name: 'Detection Accuracy',
    definition: 'Overall percentage of data quality issues correctly identified by the pipeline.',
    interpretation: 'Shows how well the pipeline finds problems in your data. Higher is better. For clean data, expect high accuracy with few issues detected.',
    goodRange: '> 80% for synthetic issues, varies on real-world data'
  },
  precision: {
    name: 'Precision',
    definition: 'Of all issues flagged by the pipeline, what percentage were actually real issues (not false alarms)?',
    interpretation: 'Measures false positive rate. High precision = fewer false alarms. You can trust the alerts. Low precision = noisy pipeline that over-flags problems.',
    goodRange: '> 0.8 (80%+) - you want to trust the alerts'
  },
  recall: {
    name: 'Recall',
    definition: 'Of all real issues in the data, what percentage did the pipeline actually catch?',
    interpretation: 'Measures detection completeness. High recall = fewer missed issues. Low recall = some problems slip through undetected.',
    goodRange: '> 0.8 (80%+) - you want to catch most problems'
  }
}

export default function Experiments() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDataset, setSelectedDataset] = useState<number | null>(null)
  const [scenario, setScenario] = useState('real_world')
  const [mode, setMode] = useState('compare')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [expandedMetric, setExpandedMetric] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/datasets')
      .then(res => res.json())
      .then(setDatasets)
      .catch(console.error)
  }, [])

  const handleRun = async () => {
    if (!selectedDataset) {
      setError('Please select a dataset')
      return
    }
    setRunning(true)
    setError('')
    try {
      const res = await fetch('http://localhost:8000/api/experiments/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: selectedDataset,
          scenario_name: scenario,
          mode: mode,
        }),
      })
      const data = await res.json()
      if (res.ok) {
        const expRes = await fetch(`http://localhost:8000/api/experiments/${data.experiment_id}`)
        const expData = await expRes.json()
        setResult(expData)
      } else {
        setError(data.detail || 'Failed to run experiment')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  const MetricCard = ({ label, value, metricKey, isPipeline }: { label: string; value: number; metricKey: string; isPipeline: string }) => {
    const isExpanded = expandedMetric === `${isPipeline}-${metricKey}`
    const explanation = METRIC_EXPLANATIONS[metricKey]
    const isAccuracy = metricKey === 'accuracy'
    const displayValue = isAccuracy ? (value * 100).toFixed(1) + '%' : value.toFixed(3)

    return (
      <div
        className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-lg transition-shadow"
        onClick={() => setExpandedMetric(isExpanded ? null : `${isPipeline}-${metricKey}`)}
      >
        <div className="flex justify-between items-start">
          <div>
            <p className="text-xs text-gray-600 font-semibold">{isPipeline.toUpperCase()}</p>
            <p className={`text-2xl font-bold mt-2 ${isPipeline === 'baseline' ? 'text-orange-600' : 'text-green-600'}`}>
              {displayValue}
            </p>
            <p className="text-xs text-gray-500">{label}</p>
          </div>
          <span className="text-lg text-gray-400">ℹ️</span>
        </div>

        {isExpanded && explanation && (
          <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
            <div>
              <p className="text-xs font-semibold text-gray-900">What it means:</p>
              <p className="text-xs text-gray-700 mt-1">{explanation.definition}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-900">How to interpret:</p>
              <p className="text-xs text-gray-700 mt-1">{explanation.interpretation}</p>
            </div>
            <div className="bg-blue-50 rounded p-2">
              <p className="text-xs font-semibold text-blue-900">Good range:</p>
              <p className="text-xs text-blue-800">{explanation.goodRange}</p>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Run Experiments</h1>
        <p className="text-gray-600 mt-2">Execute pipelines with different data scenarios and compare performance</p>
      </div>

      {!result ? (
        <div className="space-y-6">
          {/* Info Cards */}
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-bold text-gray-900 mb-2">📊 Test Scenarios</h3>
              <p className="text-sm text-gray-700">Test how pipelines handle different data quality issues. Each scenario injects realistic problems to measure detection accuracy.</p>
            </div>
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <h3 className="font-bold text-gray-900 mb-2">⚙️ Execution Modes</h3>
              <p className="text-sm text-gray-700"><strong>Baseline:</strong> minimal checks | <strong>Proposed:</strong> comprehensive validation | <strong>Compare:</strong> side-by-side analysis</p>
            </div>
          </div>

          {/* Recommendation */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="font-bold text-green-900 mb-2">💡 Recommended Workflow</h3>
            <ol className="text-sm text-green-800 space-y-1 list-decimal list-inside">
              <li><strong>Start with Real-World Data:</strong> Run your actual dataset (no injection) to establish a production baseline</li>
              <li><strong>Run Compare Mode:</strong> See actual latency overhead of proposed pipeline on your data</li>
              <li><strong>Test Edge Cases:</strong> Then use synthetic scenarios (duplicated, corrupted, etc.) to validate detection</li>
            </ol>
          </div>

          <div className="bg-white rounded-lg shadow p-8">
            <div className="space-y-6">
              {/* Dataset Selection */}
              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-2">Select Dataset</label>
                {datasets.length === 0 ? (
                  <p className="text-gray-600 text-sm">No datasets uploaded. <a href="/dashboard/upload" className="text-blue-600">Upload one first</a></p>
                ) : (
                  <select
                    value={selectedDataset || ''}
                    onChange={(e) => setSelectedDataset(Number(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-4 py-2"
                  >
                    <option value="">--Select Dataset--</option>
                    {datasets.map(d => (
                      <option key={d.id} value={d.id}>{d.name} ({d.row_count} rows)</option>
                    ))}
                  </select>
                )}
              </div>

              {/* Scenario */}
              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-2">Test Scenario</label>
                <select
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 mb-3"
                >
                  {SCENARIOS.map(s => (
                    <option key={s} value={s}>
                      {scenario === 'real_world' && s === 'real_world' ? '🌍 ' : ''}
                      {s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
                {SCENARIO_DESCRIPTIONS[scenario] && (
                  <div className={`rounded-lg p-3 ${
                    scenario === 'real_world' 
                      ? 'bg-green-50 border border-green-200' 
                      : 'bg-amber-50 border border-amber-200'
                  }`}>
                    <p className={`font-semibold text-sm ${
                      scenario === 'real_world' 
                        ? 'text-green-900' 
                        : 'text-amber-900'
                    }`}>
                      {SCENARIO_DESCRIPTIONS[scenario].title}
                    </p>
                    <p className={`text-sm mt-1 ${
                      scenario === 'real_world' 
                        ? 'text-green-800' 
                        : 'text-amber-800'
                    }`}>
                      {SCENARIO_DESCRIPTIONS[scenario].description}
                    </p>
                    <p className={`text-xs mt-2 ${
                      scenario === 'real_world' 
                        ? 'text-green-700' 
                        : 'text-amber-700'
                    }`}>
                      <strong>Use case:</strong> {SCENARIO_DESCRIPTIONS[scenario].useCase}
                    </p>
                  </div>
                )}
              </div>

              {/* Mode */}
              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-3">Execution Mode</label>
                <div className="space-y-2 mb-4">
                  {['baseline', 'proposed', 'compare'].map(m => (
                    <label key={m} className="flex items-center">
                      <input
                        type="radio"
                        name="mode"
                        value={m}
                        checked={mode === m}
                        onChange={(e) => setMode(e.target.value)}
                        className="mr-3"
                      />
                      <span className="text-gray-700 font-medium">{m.charAt(0).toUpperCase() + m.slice(1)}</span>
                    </label>
                  ))}
                </div>
                {MODE_DESCRIPTIONS[mode] && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <p className="font-semibold text-green-900 text-sm">{MODE_DESCRIPTIONS[mode].title}</p>
                    <p className="text-sm text-green-800 mt-1">{MODE_DESCRIPTIONS[mode].description}</p>
                    <div className="text-xs text-green-700 mt-2">
                      <strong>What it does:</strong>
                      <ul className="list-disc list-inside mt-1 space-y-1">
                        {MODE_DESCRIPTIONS[mode].behavior.map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>

              {error && <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">{error}</div>}

              <button
                onClick={handleRun}
                disabled={running || !selectedDataset}
                className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
              >
                {running ? 'Running Experiment...' : 'Run Experiment'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-green-800 font-semibold">✓ Experiment completed!</p>
          </div>

          {/* Results */}
          <div className="grid grid-cols-2 gap-6 lg:grid-cols-3">
            {result.baseline && (
              <>
                <MetricCard label="Detection Accuracy" value={result.baseline.accuracy} metricKey="accuracy" isPipeline="baseline" />
                <MetricCard label="Precision" value={result.baseline.precision} metricKey="precision" isPipeline="baseline" />
                <MetricCard label="Recall" value={result.baseline.recall} metricKey="recall" isPipeline="baseline" />
              </>
            )}

            {result.proposed && (
              <>
                <MetricCard label="Detection Accuracy" value={result.proposed.accuracy} metricKey="accuracy" isPipeline="proposed" />
                <MetricCard label="Precision" value={result.proposed.precision} metricKey="precision" isPipeline="proposed" />
                <MetricCard label="Recall" value={result.proposed.recall} metricKey="recall" isPipeline="proposed" />
              </>
            )}
          </div>

          {/* Metric Guide */}
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
            <h3 className="font-bold text-indigo-900 mb-2">📖 Metric Guide</h3>
            <p className="text-sm text-indigo-800 mb-3">Click on any metric card above to see what it means and how to interpret the results.</p>
            <div className="grid gap-2 text-xs text-indigo-800">
              <p><strong>🎯 Accuracy</strong> = How many issues found correctly</p>
              <p><strong>✅ Precision</strong> = How many flagged issues are real (not false alarms)</p>
              <p><strong>🔍 Recall</strong> = How many real issues were caught (vs. missed)</p>
            </div>
          </div>

          {result.baseline && result.proposed && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="font-bold text-gray-900 mb-3">Comparison Summary</h3>
              <div className="space-y-2 text-gray-700 text-sm">
                <p>✓ Accuracy improvement: <span className="font-bold text-green-600">{((result.proposed.accuracy - result.baseline.accuracy) * 100).toFixed(1)}%</span></p>
                <p>✓ False negatives reduced: <span className="font-bold text-green-600">{result.baseline.false_negatives - result.proposed.false_negatives}</span></p>
                <p>⚠ Latency overhead: <span className="font-bold text-yellow-600">{result.proposed.overhead.toFixed(0)}ms</span></p>
              </div>
            </div>
          )}

          <button
            onClick={() => { setResult(null); setSelectedDataset(null) }}
            className="bg-gray-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-gray-700"
          >
            Run Another Experiment
          </button>
        </div>
      )}
    </div>
  )
}