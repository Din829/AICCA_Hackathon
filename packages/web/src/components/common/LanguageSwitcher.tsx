'use client'

import { useLocale } from 'next-intl'
import { useRouter, usePathname } from '../../i18n/routing'
import { Button } from '../ui/button'

export default function LanguageSwitcher() {
  const locale = useLocale()
  const router = useRouter()
  const pathname = usePathname()

  const languages = [
    { code: 'ja', label: '日本語' },
    { code: 'en', label: 'English' },
    { code: 'zh', label: '中文' },
  ]

  const handleLanguageChange = (newLocale: string) => {
    router.push(pathname, { locale: newLocale })
  }

  return (
    <div className="flex gap-1">
      {languages.map((lang) => (
        <Button
          key={lang.code}
          variant={locale === lang.code ? 'default' : 'ghost'}
          size="sm"
          onClick={() => handleLanguageChange(lang.code)}
        >
          {lang.label}
        </Button>
      ))}
    </div>
  )
}