import { createFileRoute } from '@tanstack/react-router'
import { YouTubeImport } from '../components/YouTube/YouTubeImport'

export const Route = createFileRoute('/youtube')({
  component: YouTubeImport,
})
