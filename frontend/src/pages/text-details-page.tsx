import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Clock3, Database, MessageSquare } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { getTextDetails, toxicityQueryKeys } from '@/features/toxicity/toxicity-api'
import { ApiErrorPanel } from '@/shared/ui/api-error-panel'
import { Badge } from '@/shared/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { EmptyState } from '@/shared/ui/empty-state'
import { PageIntro } from '@/shared/ui/page-intro'
import { StatCard } from '@/shared/ui/stat-card'
import { formatDateTime, formatPercent, formatRelativeTime, formatScore } from '@/shared/lib/format'
import { getVerdictLabel } from '@/shared/lib/score'

export function TextDetailsPage() {
  const params = useParams()
  const textId = params.textId
  const textQuery = useQuery({
    queryKey: textId ? toxicityQueryKeys.textDetails(textId) : ['toxicity', 'text-details', 'missing'],
    queryFn: () => getTextDetails(textId!),
    enabled: Boolean(textId),
  })

  if (!textId) {
    return (
      <EmptyState
        title="Не указан идентификатор текста"
        description="Откройте карточку из анализа или из сценария разметки."
      />
    )
  }

  if (textQuery.isError) {
    return <ApiErrorPanel error={textQuery.error} title="Не удалось загрузить карточку текста" />
  }

  if (!textQuery.data) {
    return (
      <div className="space-y-6">
        <div className="h-20 rounded-[2rem] bg-secondary/70" />
        <div className="h-64 rounded-[2rem] bg-secondary/70" />
      </div>
    )
  }

  const text = textQuery.data

  return (
    <div className="space-y-6">
      <section className="space-y-4">
        <PageIntro
          eyebrow="Карточка текста"
          title="Подробная информация по сохранённому тексту"
          description="Здесь собраны исходный текст, последняя оценка модели и история пользовательских голосов."
        />
        <div className="grid gap-3 sm:grid-cols-3">
          <DetailStat label="ID текста" value={text.textId.slice(0, 8)} />
          <DetailStat label="Запросы" value={text.requestCount.toString()} />
          <DetailStat label="Длина" value={`${text.textLength} симв.`} />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
        <Card className="border-border/70">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Текст</CardTitle>
                <CardDescription>Создан {formatDateTime(text.createdAt)}, последний раз использовался {formatRelativeTime(text.lastSeenAt)}</CardDescription>
              </div>
              <Badge variant={text.lastLabel === 1 ? 'warning' : 'success'}>{getVerdictLabel(text.lastLabel)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="rounded-[1.75rem] border border-border/70 bg-surface-soft p-6 text-base leading-8 text-foreground">
              {text.text}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <StatCard label="Последняя вероятность токсичности" value={formatPercent(text.lastToxicProbability)} icon={<BarChart3 className="size-5" />} />
              <StatCard label="Версия модели" value={text.model.modelVersion} icon={<Database className="size-5" />} />
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Голоса</CardTitle>
              <CardDescription>Сводка пользовательских оценок по этому тексту.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <StatCard label="Токсичный" value={text.votesToxic.toString()} icon={<MessageSquare className="size-5" />} />
              <StatCard label="Нетоксичный" value={text.votesNonToxic.toString()} icon={<MessageSquare className="size-5" />} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Сведения</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <DetailRow label="Ключ модели" value={text.model.modelKey} />
              <DetailRow label="Версия модели" value={text.model.modelVersion} />
              <DetailRow label="Последний score" value={formatScore(text.lastToxicProbability)} />
              <DetailRow label="Создан" value={formatDateTime(text.createdAt)} />
              <DetailRow label="Последняя активность" value={`${formatDateTime(text.lastSeenAt)} (${formatRelativeTime(text.lastSeenAt)})`} />
              <DetailRow label="Количество запросов" value={text.requestCount.toString()} />
              <DetailRow label="Длина текста" value={text.textLength.toString()} />
              <DetailRow label="Идентификатор" value={text.textId} icon={<Clock3 className="size-4" />} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-surface-soft/70 p-4">
      <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-foreground">{value}</div>
    </div>
  )
}

function DetailRow({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
      <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{label}</div>
      <div className="mt-2 flex items-center gap-2 break-all font-medium text-foreground">
        {icon}
        {value}
      </div>
    </div>
  )
}
