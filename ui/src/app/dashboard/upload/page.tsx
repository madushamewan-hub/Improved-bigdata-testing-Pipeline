'use client'

import { useRef, useState } from 'react'
import Link from 'next/link'

export default function Upload() {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<any>(null)
  const [error, setError] = useState('')

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped && dropped.name.endsWith('.csv')) {
      setFile(dropped)
      setError('')
    } else {
      setError('Please drop a CSV file')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed with server error')
      }
      setPreview(data)
      setFile(null)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Upload Dataset</h1>
        <p className="text-gray-600 mt-2">Upload a CSV file to run experiments</p>
      </div>

      <div className="bg-white rounded-lg shadow p-8">
        {!preview ? (
          <>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center cursor-pointer hover:border-blue-500 transition"
            >
              <p className="text-4xl mb-2">📁</p>
              <p className="font-semibold text-gray-900">Drag and drop your CSV file here</p>
              <p className="text-gray-600 text-sm mt-1">or click to browse</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={(e) => {
                  if (e.target.files?.[0]) {
                    setFile(e.target.files[0])
                    setError('')
                  }
                }}
                className="hidden"
                id="file-input"
              />
            </div>
            {file && (
              <div className="mt-4">
                <p className="text-sm text-gray-600"><strong>Selected:</strong> {file.name}</p>
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {uploading ? 'Uploading...' : 'Upload File'}
                </button>
              </div>
            )}
            {error && <p className="mt-4 text-red-600">{error}</p>}
          </>
        ) : (
          <div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
              <p className="text-green-800 font-semibold">✓ File uploaded successfully!</p>
            </div>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-600"><strong>Dataset:</strong> {preview.name}</p>
                <p className="text-sm text-gray-600"><strong>Rows:</strong> {preview.row_count}</p>
                <p className="text-sm text-gray-600"><strong>Columns:</strong> {Object.keys(preview.schema).length}</p>
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900 mb-2">Schema:</p>
                <div className="space-y-1">
                  {Object.entries(preview.schema).map(([col, type]: any) => (
                    <p key={col} className="text-xs text-gray-600">{col}: {type}</p>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900 mb-2">Preview:</p>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-xs border">
                    <thead className="bg-gray-100">
                      <tr>
                        {Object.keys(preview.schema).map(col => (
                          <th key={col} className="px-3 py-2 text-left">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.preview.map((row: any, i: number) => (
                        <tr key={i} className="border-t">
                          {Object.keys(preview.schema).map(col => (
                            <td key={col} className="px-3 py-2">{String(row[col]).substring(0, 20)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="pt-4 space-x-3">
                <Link href="/dashboard/experiments" className="bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-blue-700 inline-block">
                  Run Experiment
                </Link>
                <button
                  onClick={() => setPreview(null)}
                  className="bg-gray-300 text-gray-900 px-6 py-2 rounded-lg font-semibold hover:bg-gray-400"
                >
                  Upload Another
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}