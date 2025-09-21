'use client'

export default function DebugPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL
  
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Debug Info</h1>
      <div className="space-y-2">
        <p><strong>API URL:</strong> {apiUrl || 'undefined'}</p>
        <p><strong>WS URL:</strong> {wsUrl || 'undefined'}</p>
        <p><strong>NODE_ENV:</strong> {process.env.NODE_ENV}</p>
      </div>
    </div>
  )
}
