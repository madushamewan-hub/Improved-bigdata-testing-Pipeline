'use client'

import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface MetricsData {
  scenario: string;
  baseline_latency: number;
  proposed_latency: number;
  precision: number;
  recall: number;
  false_positives: number;
  false_negatives: number;
}

interface MetricsChartProps {
  data: MetricsData[];
}

export default function MetricsChart({ data }: MetricsChartProps) {
  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-semibold mb-4">Latency Comparison</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="scenario" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="baseline_latency" fill="#8884d8" name="Baseline Latency" />
            <Bar dataKey="proposed_latency" fill="#82ca9d" name="Proposed Latency" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-4">Precision and Recall</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="scenario" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="precision" fill="#ffc658" name="Precision" />
            <Bar dataKey="recall" fill="#ff7300" name="Recall" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div>
        <h3 className="text-lg font-semibold mb-4">False Positives and Negatives</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="scenario" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="false_positives" fill="#d084d0" name="False Positives" />
            <Bar dataKey="false_negatives" fill="#84d0d0" name="False Negatives" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}