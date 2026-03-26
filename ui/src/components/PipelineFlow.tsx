'use client'

import React from 'react';
import ReactFlow, { Node, Edge, Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';
import { CSSProperties } from 'react';

const baselineNodes: Node[] = [
  { id: '1', position: { x: 100, y: 100 }, data: { label: 'Ingestion' }, style: { background: '#e1f5ff', padding: '20px', borderRadius: '8px' } },
  { id: '2', position: { x: 100, y: 200 }, data: { label: 'Transformation' }, style: { background: '#e1f5ff', padding: '20px', borderRadius: '8px' } },
  { id: '3', position: { x: 100, y: 300 }, data: { label: 'Storage' }, style: { background: '#e1f5ff', padding: '20px', borderRadius: '8px' } },
  { id: '4', position: { x: 100, y: 400 }, data: { label: 'Downstream' }, style: { background: '#e1f5ff', padding: '20px', borderRadius: '8px' } },
];

const baselineEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2' },
  { id: 'e2-3', source: '2', target: '3' },
  { id: 'e3-4', source: '3', target: '4' },
];

const proposedNodes: Node[] = [
  { id: 'p1', position: { x: 100, y: 100 }, data: { label: 'Ingestion\n(Schema/Null Check)' }, style: { background: '#c8e6c9', padding: '20px', borderRadius: '8px' } },
  { id: 'p2', position: { x: 100, y: 200 }, data: { label: 'Preprocessing\n(Duplicate/Checksum)' }, style: { background: '#c8e6c9', padding: '20px', borderRadius: '8px' } },
  { id: 'p3', position: { x: 100, y: 300 }, data: { label: 'Transformation\n(Validation)' }, style: { background: '#c8e6c9', padding: '20px', borderRadius: '8px' } },
  { id: 'p4', position: { x: 100, y: 400 }, data: { label: 'Storage\n(Row Count/Checksum)' }, style: { background: '#c8e6c9', padding: '20px', borderRadius: '8px' } },
  { id: 'p5', position: { x: 100, y: 500 }, data: { label: 'Downstream\n(Reconciliation)' }, style: { background: '#c8e6c9', padding: '20px', borderRadius: '8px' } },
];

const proposedEdges: Edge[] = [
  { id: 'ep1-2', source: 'p1', target: 'p2' },
  { id: 'ep2-3', source: 'p2', target: 'p3' },
  { id: 'ep3-4', source: 'p3', target: 'p4' },
  { id: 'ep4-5', source: 'p4', target: 'p5' },
];

export default function PipelineFlow() {
  return (
    <div className="flex space-x-8">
      <div className="w-1/2">
        <h3 className="text-lg font-semibold mb-4">Baseline Pipeline</h3>
        <div style={{ height: 500 }}>
          <ReactFlow nodes={baselineNodes} edges={baselineEdges}>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      </div>
      <div className="w-1/2">
        <h3 className="text-lg font-semibold mb-4">Proposed Pipeline</h3>
        <div style={{ height: 500 }}>
          <ReactFlow nodes={proposedNodes} edges={proposedEdges}>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}