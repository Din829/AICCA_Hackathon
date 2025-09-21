import { setRequestLocale } from 'next-intl/server'
import MainLayout from '../../components/layout/MainLayout'

type Props = {
  params: Promise<{ locale: string }>
}

export default async function HomePage({ params }: Props) {
  const { locale } = await params
  setRequestLocale(locale)

  return <MainLayout />
}