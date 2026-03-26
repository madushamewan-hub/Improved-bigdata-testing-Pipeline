'use client'

import React, { ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: '📊' },
  { name: 'Pipeline Flows', href: '/dashboard/flows', icon: '⚙️' },
  { name: 'Upload Data', href: '/dashboard/upload', icon: '📤' },
  { name: 'Run Experiments', href: '/dashboard/experiments', icon: '🧪' },
  { name: 'Results Comparison', href: '/dashboard/results', icon: '📈' },
  { name: 'Stage-Level Checks', href: '/dashboard/stage-checks', icon: '✓' },
  { name: 'History', href: '/dashboard/history', icon: '📜' },
  { name: 'DB View', href: '/dashboard/db', icon: '🗄️' },
  { name: 'Reports', href: '/dashboard/reports', icon: '📋' },
]

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white shadow-lg">
        <div className="p-6">
          <h1 className="text-2xl font-bold">Integrity Testing</h1>
          <p className="text-gray-400 text-sm mt-1">Thesis Dashboard</p>
        </div>
        <nav className="space-y-2 px-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-4 py-3 rounded-lg font-medium transition ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800'
                }`}
              >
                <span className="mr-2">{item.icon}</span>
                {item.name}
              </Link>
            )
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
  )
}