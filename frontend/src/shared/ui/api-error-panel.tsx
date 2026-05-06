import { AlertCircle } from 'lucide-react'
import { ApiError } from '@/shared/api/client'
import { formatProblemErrorItem } from '@/shared/api/error-resolver'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'

interface ApiErrorPanelProps {
  error: unknown
  title?: string
}

export function ApiErrorPanel({ error, title = 'Не удалось выполнить запрос' }: ApiErrorPanelProps) {
  const apiError = error instanceof ApiError ? error : null
  const errors = apiError?.problem?.errors ?? []

  return (
    <Alert variant="danger">
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 size-4 shrink-0 text-danger" />
        <div className="space-y-2">
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>
            {apiError?.message ?? apiError?.problem?.detail ?? 'Сервер вернул неожиданную ошибку.'}
          </AlertDescription>
          {errors.length > 0 ? (
            <ul className="space-y-1 text-sm text-muted-foreground">
              {errors.map((item) => (
                <li key={`${item.field}-${item.message}`}>{formatProblemErrorItem(item)}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </Alert>
  )
}
