'use client'

import { useEffect, useState } from 'react'

interface Dataset {
  id: number
  name: string
  row_count: number
}

interface PipelineStage {
  name: string
  icon: string
}

const PIPELINE_STAGES: PipelineStage[] = [
  { name: 'Ingestion', icon: '📥' },
  { name: 'Preprocessing', icon: '🧹' },
  { name: 'Transformation', icon: '⚙️' },
  { name: 'Storage', icon: '💾' },
  { name: 'Output', icon: '📤' },
]

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

type ScenarioMetricKey = 'detected_duplicates' | 'detected_loss' | 'detected_corruption' | 'detected_inconsistency'

const getTotalDetectedIssues = (pipeline: any) => (
  (pipeline?.detected_duplicates ?? 0)
  + (pipeline?.detected_loss ?? 0)
  + (pipeline?.detected_corruption ?? 0)
  + (pipeline?.detected_inconsistency ?? 0)
)

const getScenarioSummaryConfig = (scenarioName: string, detectionLabel?: string) => {
  switch (scenarioName) {
    case 'duplicated':
      return {
        metricKey: 'detected_duplicates' as ScenarioMetricKey,
        title: 'Duplicate Rows Detected',
        description: 'Rows flagged as duplicates for this duplication test.'
      }
    case 'dropped':
      return {
        metricKey: 'detected_loss' as ScenarioMetricKey,
        title: 'Dropped Rows Detected',
        description: 'Rows flagged as missing, dropped, or null-affected.'
      }
    case 'corrupted':
      return {
        metricKey: 'detected_corruption' as ScenarioMetricKey,
        title: 'Corrupted Rows Detected',
        description: 'Rows flagged with invalid or corrupted values.'
      }
    case 'schema_drift':
      return {
        metricKey: 'detected_inconsistency' as ScenarioMetricKey,
        title: 'Schema Issues Detected',
        description: 'Schema mismatches and downstream inconsistencies found.'
      }
    case 'out_of_order':
      return {
        metricKey: 'detected_inconsistency' as ScenarioMetricKey,
        title: 'Ordering Issues Detected',
        description: 'Ordering or downstream consistency issues found for sequence drift.'
      }
    case 'mixed':
      return {
        metricKey: null,
        title: 'Mixed-Issue Findings',
        description: 'Combined findings across duplicates, loss, corruption, and inconsistency.'
      }
    case 'clean':
      return {
        metricKey: null,
        title: 'Unexpected Issues Detected',
        description: 'Any issues detected in clean synthetic data should be reviewed.'
      }
    case 'real_world':
      return {
        metricKey: null,
        title: detectionLabel ? `${detectionLabel.replace(/^./, (char) => char.toUpperCase())}` : 'Detected Quality Issues',
        description: 'Quality findings detected in the uploaded dataset with no synthetic injection.'
      }
    default:
      return {
        metricKey: null,
        title: detectionLabel ? `${detectionLabel.replace(/^./, (char) => char.toUpperCase())}` : 'Detected Issues',
        description: 'Scenario-specific findings detected by the pipeline.'
      }
  }
}

const getScenarioDetectedCount = (pipeline: any, scenarioName: string) => {
  const config = getScenarioSummaryConfig(scenarioName)
  return config.metricKey ? (pipeline?.[config.metricKey] ?? 0) : getTotalDetectedIssues(pipeline)
}

const formatPercent = (value: number | null | undefined, decimals = 2) => `${Number(value ?? 0).toFixed(decimals)}%`

// Progress component to show pipeline execution stages
const ProgressLoading = ({ mode, baselineStage, proposedStage, totalProgress }: any) => {
  return (
    <div className="bg-white rounded-lg shadow p-8 space-y-8">
      {/* Overall Progress */}
      <div>
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-bold text-gray-900">Overall Progress</h3>
          <span className="text-lg font-bold text-blue-600">{Math.round(totalProgress)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className="bg-blue-600 h-full transition-all duration-300 rounded-full"
            style={{ width: `${Math.min(totalProgress, 100)}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Baseline Pipeline */}
        <div>
          <div className="flex items-center mb-4">
            <span className="text-2xl mr-2">🏪</span>
            <h3 className="font-bold text-gray-900">Baseline Pipeline</h3>
            <span className="ml-auto text-sm font-semibold text-orange-600">{baselineStage}/{PIPELINE_STAGES.length}</span>
          </div>
          <div className="space-y-2">
            {PIPELINE_STAGES.map((stage, idx) => {
              const isActive = idx === baselineStage
              const isCompleted = idx < baselineStage
              return (
                <div
                  key={`baseline-${idx}`}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    isCompleted
                      ? 'border-orange-500 bg-orange-50'
                      : isActive
                      ? 'border-orange-400 bg-orange-100 shadow-md'
                      : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{stage.icon}</span>
                    <div className="flex-1">
                      <p className={`font-semibold ${isActive ? 'text-orange-700' : isCompleted ? 'text-orange-600' : 'text-gray-600'}`}>
                        {stage.name}
                      </p>
                      {isActive && <p className="text-xs text-orange-600 mt-1">Processing...</p>}
                      {isCompleted && <p className="text-xs text-orange-600 mt-1">✓ Completed</p>}
                    </div>
                    {isActive && (
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" />
                        <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }} />
                        <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }} />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Proposed Pipeline */}
        {(mode === 'compare' || mode === 'proposed') && (
          <div>
            <div className="flex items-center mb-4">
              <span className="text-2xl mr-2">🚀</span>
              <h3 className="font-bold text-gray-900">Proposed Pipeline</h3>
              <span className="ml-auto text-sm font-semibold text-green-600">{proposedStage}/{PIPELINE_STAGES.length}</span>
            </div>
            <div className="space-y-2">
              {PIPELINE_STAGES.map((stage, idx) => {
                const isActive = idx === proposedStage
                const isCompleted = idx < proposedStage
                return (
                  <div
                    key={`proposed-${idx}`}
                    className={`p-3 rounded-lg border-2 transition-all ${
                      isCompleted
                        ? 'border-green-500 bg-green-50'
                        : isActive
                        ? 'border-green-400 bg-green-100 shadow-md'
                        : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{stage.icon}</span>
                      <div className="flex-1">
                        <p className={`font-semibold ${isActive ? 'text-green-700' : isCompleted ? 'text-green-600' : 'text-gray-600'}`}>
                          {stage.name}
                        </p>
                        {isActive && <p className="text-xs text-green-600 mt-1">Processing...</p>}
                        {isCompleted && <p className="text-xs text-green-600 mt-1">✓ Completed</p>}
                      </div>
                      {isActive && (
                        <div className="flex gap-1">
                          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }} />
                          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }} />
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Info Message */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          ⏱️ <strong>Execution in progress</strong> — Pipelines are processing your data through multiple quality validation stages. This usually takes a few seconds for large datasets.
        </p>
      </div>
    </div>
  )
}

export default function Experiments() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [engineCapabilities, setEngineCapabilities] = useState<any>(null)
  const [selectedDataset, setSelectedDataset] = useState<number | null>(null)
  const [scenario, setScenario] = useState('real_world')
  const [mode, setMode] = useState('compare')
  const [engine, setEngine] = useState('python')
  const [forceFullScan, setForceFullScan] = useState(false)
  const [sampleRate, setSampleRate] = useState<number>(100)
  const [maxWorkers, setMaxWorkers] = useState<number>(4)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const [expandedMetric, setExpandedMetric] = useState<string | null>(null)
  const [showAdvancedInfo, setShowAdvancedInfo] = useState(false)
  const [baselineStage, setBaselineStage] = useState<number>(0)
  const [proposedStage, setProposedStage] = useState<number>(0)
  const [totalProgress, setTotalProgress] = useState<number>(0)

  const activeScenario = result?.scenario || scenario
  const scenarioSummary = getScenarioSummaryConfig(activeScenario, result?.detection_label)
  const baselineScenarioCount = getScenarioDetectedCount(result?.baseline, activeScenario)
  const proposedScenarioCount = getScenarioDetectedCount(result?.proposed, activeScenario)
  const proposedOtherCount = Math.max(0, getTotalDetectedIssues(result?.proposed) - proposedScenarioCount)

  useEffect(() => {
    Promise.all([
      fetch('http://localhost:8000/api/datasets').then(res => res.json()),
      fetch('http://localhost:8000/api/runtime/engines').then(res => res.json()),
    ])
      .then(([datasetData, capabilityData]) => {
        setDatasets(datasetData)
        setEngineCapabilities(capabilityData)
        if (!capabilityData?.spark?.available) {
          setEngine('python')
        }
      })
      .catch(console.error)
  }, [])

  const handleRun = async () => {
    if (!selectedDataset) {
      setError('Please select a dataset')
      return
    }
    setRunning(true)
    setError('')
    setBaselineStage(0)
    setProposedStage(0)
    setTotalProgress(0)

    // Simulate progress updates
    const progressInterval = setInterval(() => {
      setTotalProgress(prev => {
        if (prev < 95) return prev + Math.random() * 15
        return prev
      })
    }, 500)

    // Simulate baseline stages  
    let baselineIdx = 0
    const baselineInterval = setInterval(() => {
      if (baselineIdx < 4) {
        baselineIdx++
        setBaselineStage(baselineIdx)
      }
    }, mode === 'compare' ? 1200 : 800)

    // Simulate proposed stages
    let proposedIdx = 0
    let proposedInterval: NodeJS.Timeout | null = null
    if (mode === 'compare' || mode === 'proposed') {
      proposedInterval = setInterval(() => {
        if (proposedIdx < 4) {
          proposedIdx++
          setProposedStage(proposedIdx)
        }
      }, 1400)
    }

    try {
      const res = await fetch('http://localhost:8000/api/experiments/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: selectedDataset,
          scenario_name: scenario,
          mode: mode,
          force_full_scan: forceFullScan,
          engine: engine,
          sample_rate: Number((sampleRate || 100) / 100),
          max_workers: Number(maxWorkers || 4),
        }),
      })
      const data = await res.json()
      if (res.ok) {
        const expRes = await fetch(`http://localhost:8000/api/experiments/${data.experiment_id}`)
        const expData = await expRes.json()
        setResult(expData)
        setTotalProgress(100)
      } else {
        setError(data.detail || 'Failed to run experiment')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      clearInterval(progressInterval)
      clearInterval(baselineInterval)
      if (proposedInterval) clearInterval(proposedInterval)
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

      {running ? (
        <ProgressLoading mode={mode} baselineStage={baselineStage} proposedStage={proposedStage} totalProgress={totalProgress} />
      ) : !result ? (
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

              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-3">Execution Engine</label>
                <div className="space-y-2 mb-4">
                  <label className="flex items-start">
                    <input
                      type="radio"
                      name="engine"
                      value="python"
                      checked={engine === 'python'}
                      onChange={(e) => setEngine(e.target.value)}
                      className="mt-1 mr-3"
                    />
                    <div>
                      <span className="text-gray-700 font-medium">Python Reference Engine</span>
                      <p className="text-xs text-gray-500 mt-1">Stable local execution for the integrity testing framework.</p>
                    </div>
                  </label>
                  <label className={`flex items-start ${engineCapabilities?.spark?.available ? '' : 'opacity-60'}`}>
                    <input
                      type="radio"
                      name="engine"
                      value="spark"
                      checked={engine === 'spark'}
                      onChange={(e) => setEngine(e.target.value)}
                      className="mt-1 mr-3"
                      disabled={!engineCapabilities?.spark?.available}
                    />
                    <div>
                      <span className="text-gray-700 font-medium">Spark Adapter Engine</span>
                      <p className="text-xs text-gray-500 mt-1">
                        {engineCapabilities?.spark?.reason || 'Distributed execution adapter for comparative benchmarking.'}
                      </p>
                      {engineCapabilities?.spark?.alternate_python && (
                        <p className="text-xs text-emerald-700 mt-1">Using alternate Spark Python: {engineCapabilities.spark.alternate_python}</p>
                      )}
                    </div>
                  </label>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs text-slate-700 space-y-1">
                  <p>Engine selection applies to the proposed pipeline path. Baseline remains the lightweight reference comparator.</p>
                  <p>
                    <strong>Backend Python environment:</strong>{' '}
                    {engineCapabilities?.spark?.current_python || engineCapabilities?.python?.current_python || 'unknown'}
                  </p>
                  <p>
                    <strong>Spark requirement:</strong> the Spark adapter is enabled only when the backend is running on a compatible Python{' '}
                    {engineCapabilities?.spark?.recommended_python || '3.11/3.12'} runtime, or when <code>SPARK_PYTHON_EXECUTABLE</code> points to one.
                  </p>
                  {!engineCapabilities?.spark?.available && (
                    <p className="text-amber-700">
                      If Spark is disabled, the active backend Python version does not match the required runtime or the alternate Spark Python path is not configured.
                    </p>
                  )}
                </div>
              </div>

              {/* Sampling & Parallelism */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-4">
                <label className="block text-sm font-semibold text-gray-900 mb-2">Sampling & Parallelism</label>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-600">Sample Rate (%)</p>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={sampleRate}
                      onChange={(e) => setSampleRate(Number(e.target.value))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    />
                    <p className="text-xs text-gray-500 mt-1">Lower sample speeds up runs (approximate results).</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Parser Workers</p>
                    <input
                      type="number"
                      min={1}
                      max={32}
                      value={maxWorkers}
                      onChange={(e) => setMaxWorkers(Number(e.target.value))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    />
                    <p className="text-xs text-gray-500 mt-1">Increase for more parallel parsing.</p>
                  </div>
                </div>
              </div>

              {/* Force Full Scan Option */}
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={forceFullScan}
                    onChange={(e) => setForceFullScan(e.target.checked)}
                    className="mt-1 mr-3"
                  />
                  <div>
                    <p className="font-semibold text-yellow-900 text-sm">🔍 Force Full Scan</p>
                    <p className="text-yellow-800 text-xs mt-1">
                      For large datasets that were processed in limited mode, force complete analysis of all rows.
                      This may take significantly longer and use more memory.
                    </p>
                    <p className="text-yellow-700 text-xs mt-1">
                      Only enable if you need definitive results for the entire dataset.
                    </p>
                  </div>
                </label>
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
            <p className="text-sm text-green-700 mt-1">Detection label: <span className="font-semibold">{result.detection_label || result.scenario}</span> • Actual amended rows: <span className="font-semibold">{result.actual_amended_count || 0}</span></p>
          </div>

          {/* Processing Mode Warning */}
          {result.dataset_info && result.dataset_info.truncated && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex items-start">
                <span className="text-yellow-600 text-xl mr-3">⚠️</span>
                <div>
                  <p className="text-yellow-800 font-semibold">Limited Processing Mode</p>
                  <p className="text-yellow-700 text-sm mt-1">
                    This dataset was too large to process fully. Only {result.dataset_info.rows_processed.toLocaleString()} of {result.dataset_info.total_rows.toLocaleString()} rows were analyzed.
                    Results are approximate and may not reflect the complete dataset.
                  </p>
                  <p className="text-yellow-700 text-xs mt-2">
                    For complete analysis, consider using a smaller dataset or contact support for full processing options.
                  </p>
                </div>
              </div>
            </div>
          )}

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

          {result.proposed && (
            <div className="space-y-6">
              <div className="bg-white rounded-lg shadow p-6 border border-sky-200">
                <h3 className="font-bold text-gray-900 mb-4">Issue Counts: Injected vs Detected</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-sky-50 rounded-lg p-4 border border-sky-200">
                    <p className="text-xs text-sky-800 font-semibold">Actual Amended Rows</p>
                    <p className="text-2xl font-bold text-sky-700 mt-1">{result.actual_amended_count || 0}</p>
                    <p className="text-xs text-sky-700 mt-1">Rows actually changed by the selected scenario</p>
                  </div>
                  {result.baseline && (
                    <div className="bg-orange-50 rounded-lg p-4 border border-orange-200">
                      <p className="text-xs text-orange-800 font-semibold">Baseline {scenarioSummary.title}</p>
                      <p className="text-2xl font-bold text-orange-700 mt-1">{baselineScenarioCount}</p>
                      <p className="text-xs text-orange-700 mt-1">{scenarioSummary.description}</p>
                    </div>
                  )}
                  <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-200">
                    <p className="text-xs text-emerald-800 font-semibold">Proposed {scenarioSummary.title}</p>
                    <p className="text-2xl font-bold text-emerald-700 mt-1">{proposedScenarioCount}</p>
                    <p className="text-xs text-emerald-700 mt-1">{scenarioSummary.description}</p>
                  </div>
                  <div className="bg-violet-50 rounded-lg p-4 border border-violet-200">
                    <p className="text-xs text-violet-800 font-semibold">Other Detected Issues</p>
                    <p className="text-2xl font-bold text-violet-700 mt-1">{proposedOtherCount}</p>
                    <p className="text-xs text-violet-700 mt-1">Additional findings outside the primary selected scenario.</p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-6 border border-emerald-200">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-gray-900">Advanced Evaluation (Step 1-4)</h3>
                  <button
                    type="button"
                    onClick={() => setShowAdvancedInfo(prev => !prev)}
                    className="text-sm px-3 py-1 rounded-full border border-gray-300 text-gray-700 hover:bg-gray-50"
                    title="Show score meanings"
                  >
                    ℹ️ Score Meaning
                  </button>
                </div>

                {showAdvancedInfo && (
                  <div className="mb-4 bg-slate-50 border border-slate-200 rounded-lg p-4 text-sm text-slate-700 space-y-2">
                    <p><strong>Composite Score</strong> combines dimension quality and sector target performance.</p>
                    <p><strong>Formula:</strong> Composite = 0.6 × Dimension Average + 0.4 × Sector Compliance.</p>
                    <p><strong>Dimension Average</strong> is the mean score across the 9 core dimensions (accuracy, completeness, consistency, validity, uniqueness, timeliness, integrity, reliability, traceability/governance).</p>
                    <p><strong>Sector Compliance</strong> reflects pass-rate and attainment against the 15 advanced metric targets for the selected sector profile.</p>
                    <p><strong>Industry-Level Metrics</strong> below expose the exact thesis formulas for DDR, FPR, FNR, TRC, CCE, DA, RSR, and latency overhead.</p>
                    <p><strong>Interpretation:</strong> 90-100% excellent, 75-89% strong, 60-74% moderate, below 60% needs improvement.</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-200">
                    <p className="text-xs text-emerald-800 font-semibold">Composite Score</p>
                    <p className="text-2xl font-bold text-emerald-700 mt-1">{((result.proposed.composite_score || 0) * 100).toFixed(1)}%</p>
                    <p className="text-xs text-emerald-700 mt-1">{result.proposed.composite_formula || '0.6*dimension_average + 0.4*sector_compliance'}</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <p className="text-xs text-blue-800 font-semibold">Dimension Average</p>
                    <p className="text-2xl font-bold text-blue-700 mt-1">{((result.proposed.dimension_average_score || 0) * 100).toFixed(1)}%</p>
                    <p className="text-xs text-blue-700 mt-1">9-core-dimension aggregate</p>
                  </div>
                  <div className="bg-violet-50 rounded-lg p-4 border border-violet-200">
                    <p className="text-xs text-violet-800 font-semibold">Sector Compliance</p>
                    <p className="text-2xl font-bold text-violet-700 mt-1">{((result.proposed.sector_compliance_score || 0) * 100).toFixed(1)}%</p>
                    <p className="text-xs text-violet-700 mt-1">Sector: {(result.proposed.sector || 'cross_industry').replace(/_/g, ' ')}</p>
                  </div>
                </div>
                <div className="mt-3 text-xs text-gray-600">Engine used: <span className="font-semibold text-gray-900">{(result.proposed.engine || result.engine || engine || 'python').replace(/_/g, ' ')}</span></div>

                <div className="mt-4">
                  <p className="text-xs font-semibold text-slate-800 mb-3">Industry-Level Evaluation</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                    <div className="bg-green-50 rounded-lg p-3 border border-green-200">
                      <p className="text-xs text-green-800 font-semibold">DDR</p>
                      <p className="text-lg font-bold text-green-700 mt-1">{formatPercent(result.proposed.defect_detection_rate, 2)}</p>
                      <p className="text-[11px] text-green-700 mt-1">Detected integrity issues / total actual issues</p>
                    </div>
                    <div className="bg-rose-50 rounded-lg p-3 border border-rose-200">
                      <p className="text-xs text-rose-800 font-semibold">FPR</p>
                      <p className="text-lg font-bold text-rose-700 mt-1">{formatPercent(result.proposed.false_positive_rate, 2)}</p>
                      <p className="text-[11px] text-rose-700 mt-1">Incorrectly flagged valid cases</p>
                    </div>
                    <div className="bg-orange-50 rounded-lg p-3 border border-orange-200">
                      <p className="text-xs text-orange-800 font-semibold">FNR</p>
                      <p className="text-lg font-bold text-orange-700 mt-1">{formatPercent(result.proposed.false_negative_rate, 2)}</p>
                      <p className="text-[11px] text-orange-700 mt-1">Missed integrity issues</p>
                    </div>
                    <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                      <p className="text-xs text-blue-800 font-semibold">TRC</p>
                      <p className="text-lg font-bold text-blue-700 mt-1">{formatPercent(result.proposed.transformation_rule_coverage, 2)}</p>
                      <p className="text-[11px] text-blue-700 mt-1">Validated transformation rules / total rules</p>
                    </div>
                    <div className="bg-cyan-50 rounded-lg p-3 border border-cyan-200">
                      <p className="text-xs text-cyan-800 font-semibold">CCE</p>
                      <p className="text-lg font-bold text-cyan-700 mt-1">{formatPercent(result.proposed.completeness_check_effectiveness, 2)}</p>
                      <p className="text-[11px] text-cyan-700 mt-1">Correctly detected incomplete records</p>
                    </div>
                    <div className="bg-violet-50 rounded-lg p-3 border border-violet-200">
                      <p className="text-xs text-violet-800 font-semibold">DA</p>
                      <p className="text-lg font-bold text-violet-700 mt-1">{formatPercent(result.proposed.deduplication_accuracy, 2)}</p>
                      <p className="text-[11px] text-violet-700 mt-1">Correct duplicate decisions</p>
                    </div>
                    <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                      <p className="text-xs text-amber-800 font-semibold">RSR</p>
                      <p className="text-lg font-bold text-amber-700 mt-1">{formatPercent(result.proposed.recovery_success_rate, 2)}</p>
                      <p className="text-[11px] text-amber-700 mt-1">Successful recoveries / recovery attempts</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                      <p className="text-xs text-slate-800 font-semibold">Latency Overhead</p>
                      <p className="text-lg font-bold text-slate-700 mt-1">{formatPercent(result.proposed.latency_overhead_percent, 2)}</p>
                      <p className="text-[11px] text-slate-700 mt-1">Relative to baseline latency</p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mt-4">
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                    <p className="text-xs text-gray-600 font-semibold">Retry Attempts</p>
                    <p className="text-lg font-bold text-gray-900 mt-1">{result.proposed.retry_attempts || 0}</p>
                  </div>
                  <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-200">
                    <p className="text-xs text-indigo-700 font-semibold">Recovery Attempts</p>
                    <p className="text-lg font-bold text-indigo-800 mt-1">{result.proposed.recovery_attempts || 0}</p>
                  </div>
                  <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-200">
                    <p className="text-xs text-emerald-700 font-semibold">Successful Recoveries</p>
                    <p className="text-lg font-bold text-emerald-800 mt-1">{result.proposed.successful_recoveries || 0}</p>
                  </div>
                  <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                    <p className="text-xs text-amber-700 font-semibold">Quarantine Count</p>
                    <p className="text-lg font-bold text-amber-800 mt-1">{result.proposed.quarantine_count || 0}</p>
                  </div>
                  <div className="bg-cyan-50 rounded-lg p-3 border border-cyan-200">
                    <p className="text-xs text-cyan-700 font-semibold">Checkpoint Recoveries</p>
                    <p className="text-lg font-bold text-cyan-800 mt-1">{result.proposed.checkpoint_recoveries || 0}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

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
                <p>🔢 Actual amended rows: <span className="font-bold text-blue-700">{result.actual_amended_count || 0}</span></p>
                <p>🧪 Proposed {scenarioSummary.title.toLowerCase()}: <span className="font-bold text-emerald-700">{proposedScenarioCount}</span></p>
                <p>⚠ Latency overhead: <span className="font-bold text-yellow-600">{result.proposed.overhead.toFixed(0)}ms</span></p>
                <p>⭐ Composite score: <span className="font-bold text-emerald-700">{((result.proposed.composite_score || 0) * 100).toFixed(1)}%</span></p>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => window.open(`http://localhost:8000/api/experiments/${result.id}/export.xlsx`, '_blank')}
              className="bg-emerald-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-emerald-700"
            >
              Download Excel Report
            </button>
            <button
              onClick={() => { 
                setResult(null); 
                setSelectedDataset(null);
                setForceFullScan(false);
                setEngine('python');
                setShowAdvancedInfo(false);
              }}
              className="bg-gray-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-gray-700"
            >
              Run Another Experiment
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
