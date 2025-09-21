import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AICCA - AI Content Credibility Agent',
  description: 'Verify the authenticity of AI-generated content',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}