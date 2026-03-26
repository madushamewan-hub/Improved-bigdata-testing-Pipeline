'use client'

import { useEffect, useState } from 'react'
import ReactFlow, { Node, Edge, Background, Controls } from 'reactflow'
import 'reactflow/dist/style.css'

export default function PipelineFlows() {
  const [flows, setFlows] = useState<any>(null)
  const [selectedNode, setSelectedNode] = useState<any>(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/flows')
      .then(res => res.json())
      .then(data => setFlows(data))
      .catch(err => console.error('Error loading flows:', err))
  }, [])

  if (!flows) {
    return <div className="text-center text-gray-500">Loading pipeline flows...</div>
  }

  const NodeDetails = ({ node }: any) => (
    <div className="bg-white rounded-lg shadow p-4 mt-4">
      <h3 className="font-bold text-lg text-gray-900">{node.label}</h3>
      <p className="text-sm text-gray-600 mt-2"><strong>Stage:</strong> {node.stage}</p>
      <p className="text-sm text-gray-600 mt-1"><strong>Checks:</strong></p>
      <ul className="list-disc list-inside text-sm text-gray-600">
        {node.checks.map((check: string, i: number) => (
          <li key={i}>{check}</li>
        ))}
      </ul>
      {node.issue_types.length > 0 && (
        <>
          <p className="text-sm text-gray-600 mt-2"><strong>Target Issue Types:</strong></p>
          <div className="flex flex-wrap gap-2 mt-1">
            {node.issue_types.map((issue: string, i: number) => (
              <span key={i} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                {issue}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Pipeline Flow Comparison</h1>
        <p className="text-gray-600 mt-2">Click on a stage to view detailed checks and validations</p>
      </div>

      {/* Baseline Pipeline */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-3">Baseline Pipeline (Minimal Checks)</h2>
        <div style={{ width: '100%', height: '400px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <ReactFlow nodes={flows.baseline.nodes} edges={flows.baseline.edges} onNodeClick={(e, node) => setSelectedNode(node)}>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {selectedNode && flows.baseline.nodes.find((n: any) => n.id === selectedNode.id) && (
          <NodeDetails node={flows.baseline.nodes.find((n: any) => n.id === selectedNode.id)} />
        )}
      </div>

      {/* Proposed Pipeline */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-3">Proposed Pipeline (Integrity-Focused)</h2>
        <div style={{ width: '100%', height: '400px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <ReactFlow nodes={flows.proposed.nodes} edges={flows.proposed.edges} onNodeClick={(e, node) => setSelectedNode(node)}>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {selectedNode && flows.proposed.nodes.find((n: any) => n.id === selectedNode.id) && (
          <NodeDetails node={flows.proposed.nodes.find((n: any) => n.id === selectedNode.id)} />
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