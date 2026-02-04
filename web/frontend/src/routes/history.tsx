import { createFileRoute } from '@tanstack/react-router'
import { HistoryPage } from '../components/HistoryPage'

export const Route = createFileRoute('/history')({
  component: HistoryPage,
})
