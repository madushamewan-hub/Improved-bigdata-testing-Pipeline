'use client'

import { useEffect, useState } from 'react'
import ReactFlow, { Node, Edge, Background, Controls } from 'reactflow'
import 'reactflow/dist/style.css'

export default function PipelineFlows() {
  const [flows, setFlows] = useState<any>(null)
  const [selectedBaselineNode, setSelectedBaselineNode] = useState<any>(null)
  const [hoveredBaselineNode, setHoveredBaselineNode] = useState<any>(null)
  const [selectedProposedNode, setSelectedProposedNode] = useState<any>(null)
  const [hoveredProposedNode, setHoveredProposedNode] = useState<any>(null)
  const [flowError, setFlowError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/flows')
      .then(res => {
        if (!res.ok) throw new Error(`Flows API failed: ${res.statusText}`)
        return res.json()
      })
      .then(data => {
        const normalize = (n: any) => ({
          id: n.id,
          position: { x: n.x ?? 0, y: n.y ?? 0 },
          data: {
            label: n.label,
            stage: n.stage,
            checks: n.checks ?? [],
            issue_types: n.issue_types ?? [],
          },
        })

        const normalizeEdges = (edges: any[]) =>
          (edges ?? []).map((e: any, idx: number) => ({
            id: `${e.source}-${e.target}-${idx}`,
            source: e.source,
            target: e.target,
          }))

        setFlows({
          baseline: {
            nodes: (data?.baseline?.nodes ?? []).map(normalize),
            edges: normalizeEdges(data?.baseline?.edges),
          },
          proposed: {
            nodes: (data?.proposed?.nodes ?? []).map(normalize),
            edges: normalizeEdges(data?.proposed?.edges),
          },
        })
      })
      .catch(err => {
        console.error('Error loading flows:', err)
        setFlowError(err.message ?? 'Unable to load flows')
      })
  }, [])

  if (flowError) {
    return <div className="text-center text-red-500">{flowError}</div>
  }

  if (!flows || !flows.baseline || !flows.proposed) {
    return <div className="text-center text-gray-500">Loading pipeline flows...</div>
  }

  const stageDescriptions: Record<string, string> = {
    Ingestion:
      'Load raw data; perform basic schema discovery, header check, and file format validation to prevent early failure.',
    Preprocessing:
      'Clean data, deduplicate rows, and apply conversions. Detect schema drift or data gaps before transformation.',
    Transformation:
      'Apply data enrichment and rules; check type assertions and validation logic to protect downstream semantics.',
    Storage:
      'Persist output rows and run row count + checksum checks to catch persistence issues and data loss.',
    Output:
      'Perform downstream reconciliation and consistency checks to ensure endpoints match expected results.',
  }

  const NodeDetails = ({ node }: { node: any }) => {
    const stageData = node?.data ?? {}
    const checks = Array.isArray(stageData?.checks) ? stageData.checks : []
    const issues = Array.isArray(stageData?.issue_types) ? stageData.issue_types : []

    return (
      <div className="bg-white rounded-lg shadow p-4 mt-4">
        <h3 className="font-bold text-lg text-gray-900">{stageData?.label ?? 'Unknown stage'}</h3>
        <p className="text-sm text-gray-600 mt-2"><strong>Stage:</strong> {stageData?.stage ?? 'unknown'}</p>
        {stageDescriptions[stageData?.stage ?? ''] ? (
          <p className="text-sm text-gray-600 mt-1">{stageDescriptions[stageData.stage]}</p>
        ) : null}
        <p className="text-sm text-gray-600 mt-2"><strong>Checks:</strong></p>
        <ul className="list-disc list-inside text-sm text-gray-600">
          {checks.map((check: string, i: number) => (
            <li key={i}>{check}</li>
          ))}
        </ul>
        {issues.length > 0 && (
          <>
            <p className="text-sm text-gray-600 mt-2"><strong>Target Issue Types:</strong></p>
            <div className="flex flex-wrap gap-2 mt-1">
              {issues.map((issue: string, i: number) => (
                <span key={i} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                  {issue}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Pipeline Flow Comparison</h1>
        <p className="text-gray-600 mt-2">
          Hover a node for quick info. Click to lock stage details (click again to unlock).
        </p>
      </div>

      {/* Baseline Pipeline */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-3">Baseline Pipeline (Minimal Checks)</h2>
        <div style={{ width: '100%', height: '400px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <ReactFlow
            nodes={flows.baseline.nodes}
            edges={flows.baseline.edges}
            fitView={true}
            zoomOnScroll={false}
            panOnScroll={false}
            zoomOnPinch={false}
            minZoom={0.75}
            maxZoom={2}
            panOnDrag={false}
            elementsSelectable={false}
            nodesDraggable={false}
            onNodeClick={(_, node) => {
              const isSame = selectedBaselineNode?.id === node.id
              setSelectedBaselineNode(isSame ? null : node)
            }}
            onNodeMouseEnter={(_, node) => {
              if (!selectedBaselineNode) setHoveredBaselineNode(node)
            }}
            onNodeMouseLeave={() => setHoveredBaselineNode(null)}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {(selectedBaselineNode || hoveredBaselineNode) && (
          <NodeDetails node={selectedBaselineNode || hoveredBaselineNode} />
        )}
      </div>

      {/* Proposed Pipeline */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-3">Proposed Pipeline (Integrity-Focused)</h2>
        <div style={{ width: '100%', height: '400px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <ReactFlow
            nodes={flows.proposed.nodes}
            edges={flows.proposed.edges}
            fitView={true}
            zoomOnScroll={false}
            panOnScroll={false}
            zoomOnPinch={false}
            minZoom={0.75}
            maxZoom={2}
            panOnDrag={false}
            elementsSelectable={false}
            nodesDraggable={false}
            onNodeClick={(_, node) => {
              const isSame = selectedProposedNode?.id === node.id
              setSelectedProposedNode(isSame ? null : node)
            }}
            onNodeMouseEnter={(_, node) => {
              if (!selectedProposedNode) setHoveredProposedNode(node)
            }}
            onNodeMouseLeave={() => setHoveredProposedNode(null)}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {(selectedProposedNode || hoveredProposedNode) && (
          <NodeDetails node={selectedProposedNode || hoveredProposedNode} />
        )}
      </div>

      {/* Comparison Summary */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-bold text-gray-900 mb-3">Key Differences</h3>
        <div className="space-y-2 text-gray-700 text-sm">
          <p>✓ <strong>Proposed pipeline adds schema validation</strong> at ingestion stage</p>
          <p>✓ <strong>Preprocessing stage includes duplicate detection and checksums</strong></p>
          <p>✓ <strong>Storage stage checks row counts</strong> for data loss detection</p>
          <p>✓ <strong>Output stage includes downstream validation</strong> and consistency checks</p>
          <p>⚠ <strong>Trade-off:</strong> Additional checks increase latency by ~200-400ms</p>
        </div>
      </div>
    </div>
  )
}