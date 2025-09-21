import { NextIntlClientProvider } from 'next-intl'
import { getMessages, setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'
import { routing } from '../../i18n/routing'
import QueryProvider from '../../components/providers/query-provider'
import WebSocketProvider from '../../components/providers/websocket-provider'
import { Toaster } from '../../components/ui/sonner'

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  
  // 验证locale是否有效
  if (!routing.locales.includes(locale as any)) {
    notFound()
  }

  setRequestLocale(locale)
  const messages = await getMessages()

  return (
    <html lang={locale}>
      <body>
        <QueryProvider>
          <NextIntlClientProvider messages={messages}>
            <WebSocketProvider>
              {children}
              <Toaster position="bottom-right" />
            </WebSocketProvider>
          </NextIntlClientProvider>
        </QueryProvider>
      </body>
    </html>
  )
}