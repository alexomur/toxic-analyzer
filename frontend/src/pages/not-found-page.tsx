import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/shared/ui/button'
import { EmptyState } from '@/shared/ui/empty-state'

export function NotFoundPage() {
  return (
    <EmptyState
      icon={<Compass className="size-6" />}
      title="Такой страницы нет."
      description="Вернитесь к проверке текста, проверке набора или разметке данных."
      action={
        <Button asChild>
          <Link to="/">Перейти к проверке текста</Link>
        </Button>
      }
      className="py-20"
    />
  )
}
