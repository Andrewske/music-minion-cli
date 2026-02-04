import { createFileRoute } from '@tanstack/react-router'
import { ComparisonView } from '../components/ComparisonView'

export const Route = createFileRoute('/comparison')({
  component: ComparisonView,
})
