'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function DashboardNav() {
  const pathname = usePathname()

  const navItems = [
    { label: 'Overview', href: '/dashboard', icon: '📊' },
    { label: 'Experiments', href: '/dashboard/experiments', icon: '🔬' },
    { label: 'Reports', href: '/dashboard/reports', icon: '📈' },
    { label: 'Settings', href: '/dashboard/settings', icon: '⚙️' },
  ]

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center h-16">
          <Link href="/" className="mr-8">
            <span className="text-2xl font-bold text-blue-600">DQ</span>
          </Link>
          <div className="flex gap-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href || (item.href === '/dashboard' && pathname === '/dashboard')
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 ${
                    isActive
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span>{item.icon}</span>
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}