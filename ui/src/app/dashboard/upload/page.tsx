'use client'

import { useRef, useState, useEffect } from 'react'
import Link from 'next/link'

interface FileFormatInfo {
  icon: string
  label: string
  description: string
  example: string
}

export default function Upload() {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<any>(null)
  const [error, setError] = useState('')
  const [formats, setFormats] = useState<Record<string, FileFormatInfo>>({})

  useEffect(() => {
    // Fetch supported formats from backend
    fetch('http://localhost:8000/api/upload/formats')
      .then(res => res.json())
      .then(setFormats)
      .catch(console.error)
  }, [])

  const SUPPORTED_EXTENSIONS = '.csv,.json,.ndjson,.parquet,.xlsx,.xls,.tsv'

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      const ext = dropped.name.split('.').pop()?.toLowerCase()
      if (ext && SUPPORTED_EXTENSIONS.includes(ext)) {
        setFile(dropped)
        setError('')
      } else {
        setError(`Please drop a supported file format. Supported: ${SUPPORTED_EXTENSIONS.replace(/\./g, '')}`)
      }
    }
  }

  const handleUpload = async () => {
    if (!file) return
    
    // Warn if file is large
    const fileSizeMB = file.size / 1024 / 1024
    if (fileSizeMB > 100) {
      if (!window.confirm(`File is ${fileSizeMB.toFixed(1)}MB. Large files may take longer to process. Continue?`)) {
        return
      }
    }

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
        <p className="text-gray-600 mt-2">Upload data in multiple formats (CSV, JSON, Parquet, Excel, etc.)</p>
      </div>

      {!preview ? (
        <>
          {/* Format Info Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {Object.entries(formats).map(([ext, info]) => (
              <div key={ext} className="bg-white rounded-lg shadow p-3 border border-gray-200 hover:border-blue-300">
                <p className="text-2xl mb-1">{info.icon}</p>
                <p className="text-xs font-semibold text-gray-900">{info.label}</p>
                <p className="text-xs text-gray-600 mt-1">{info.description}</p>
              </div>
            ))}
          </div>

          {/* Upload Area */}
          <div className="bg-white rounded-lg shadow p-8">
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center cursor-pointer hover:border-blue-500 transition"
            >
              <p className="text-4xl mb-2">📁</p>
              <p className="font-semibold text-gray-900">Drag and drop your data file here</p>
              <p className="text-gray-600 text-sm mt-1">Supported formats: CSV, JSON, NDJSON, Parquet, Excel, TSV</p>
              <p className="text-gray-500 text-xs mt-2">Max file size: 500MB</p>
              <input
                ref={fileInputRef}
                type="file"
                accept={SUPPORTED_EXTENSIONS}
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
                <p className="text-sm text-gray-600 mt-1"><strong>Size:</strong> {(file.size / 1024 / 1024).toFixed(2)}MB</p>
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {uploading ? 'Uploading...' : 'Upload File'}
                </button>
              </div>
            )}
            {error && <p className="mt-4 text-red-600 text-sm">{error}</p>}
          </div>
        </>
      ) : (
        <div className="bg-white rounded-lg shadow p-8">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
            <p className="text-green-800 font-semibold">✓ File uploaded successfully!</p>
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-gray-500 font-semibold">Dataset Name</p>
                <p className="text-sm font-semibold text-gray-900">{preview.name}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 font-semibold">Format</p>
                <p className="text-sm font-semibold text-gray-900 uppercase">{preview.format}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 font-semibold">File Size</p>
                <p className="text-sm font-semibold text-gray-900">{preview.size_mb.toFixed(2)}MB</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 font-semibold">Rows</p>
                <p className="text-sm font-semibold text-gray-900">{preview.row_count.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 font-semibold">Columns</p>
                <p className="text-sm font-semibold text-gray-900">{Object.keys(preview.schema).length}</p>
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900 mb-2">Schema:</p>
              <div className="space-y-1 bg-gray-50 p-3 rounded max-h-40 overflow-y-auto">
                {Object.entries(preview.schema).map(([col, type]: any) => (
                  <p key={col} className="text-xs text-gray-700"><strong>{col}</strong>: {type}</p>
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
                        <th key={col} className="px-3 py-2 text-left font-semibold">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row: any, i: number) => (
                      <tr key={i} className="border-t">
                        {Object.keys(preview.schema).map(col => (
                          <td key={col} className="px-3 py-2 text-gray-700">{String(row[col]).substring(0, 25)}</td>
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
  )
}

    </div>
  )
}