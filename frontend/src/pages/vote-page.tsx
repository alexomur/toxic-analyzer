import type { ReactNode } from 'react'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRight, BarChart3, Clock3, Database, MessageSquareQuote, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '@/features/auth/auth-context'
import { getRandomText, getTextDetails, toxicityQueryKeys, voteForText } from '@/features/toxicity/toxicity-api'
import type { VoteKind } from '@/features/toxicity/toxicity-types'
import { ApiError } from '@/shared/api/client'
import { formatDateTime, formatPercent, formatRelativeTime } from '@/shared/lib/format'
import { getVerdictLabel } from '@/shared/lib/score'
import { ApiErrorPanel } from '@/shared/ui/api-error-panel'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { EmptyState } from '@/shared/ui/empty-state'
import { PageIntro } from '@/shared/ui/page-intro'
import { StatCard } from '@/shared/ui/stat-card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'

export function VotePage() {
  const { isAuthenticated } = useAuth()
  const randomTextQuery = useQuery({
    queryKey: toxicityQueryKeys.randomText,
    queryFn: getRandomText,
    retry: false,
  })
  const [submittedVote, setSubmittedVote] = useState<VoteKind | null>(null)
  const voteMutation = useMutation({
    mutationFn: ({ textId, vote }: { textId: string; vote: VoteKind }) => voteForText(textId, vote),
    onSuccess: (_, variables) => {
      setSubmittedVote(variables.vote)
      toast.success('Оценка сохранена.')
    },
  })

  const currentText = randomTextQuery.data
  const textDetailsQuery = useQuery({
    queryKey: currentText ? toxicityQueryKeys.textDetails(currentText.textId) : ['toxicity', 'text-details', 'missing'],
    queryFn: () => getTextDetails(currentText!.textId),
    enabled: Boolean(isAuthenticated && submittedVote && currentText),
  })

  return (
    <div className="space-y-6">
      <PageIntro
        eyebrow="Разметка данных"
        title="Оценивайте тексты по одному и помогайте улучшать датасет"
        description="Откройте случайный текст, выберите метку и сразу переходите к следующему примеру без лишних шагов."
      />

      {randomTextQuery.isError ? (
        randomTextQuery.error instanceof ApiError && randomTextQuery.error.status === 404 ? (
          <EmptyState
            icon={<MessageSquareQuote className="size-6" />}
            title="Для разметки пока нет доступных текстов."
            description="Сначала система должна накопить тексты, после чего они появятся в этом разделе."
          />
        ) : (
          <ApiErrorPanel error={randomTextQuery.error} title="Не удалось загрузить текст" />
        )
      ) : null}

      {currentText ? (
        <Card className="overflow-hidden border-border/70">
          <CardHeader className="border-b border-border/70 bg-card/60">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Текст для разметки</CardTitle>
                <CardDescription>Выберите подходящую метку и переходите к следующему примеру.</CardDescription>
              </div>
              {submittedVote ? (
                <Badge variant={submittedVote === 'toxic' ? 'warning' : 'success'}>
                  {submittedVote === 'toxic' ? 'Отмечен как токсичный' : 'Отмечен как нетоксичный'}
                </Badge>
              ) : (
                <Badge variant="secondary">Ждёт вашей оценки</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6 p-6">
            <div className="rounded-[1.75rem] border border-border/70 bg-surface-soft p-6 text-lg leading-8 text-foreground">
              {currentText.text}
            </div>

            {voteMutation.isError ? <ApiErrorPanel error={voteMutation.error} title="Не удалось сохранить оценку" /> : null}

            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                variant="accent"
                size="lg"
                className="flex-1"
                disabled={voteMutation.isPending || Boolean(submittedVote)}
                onClick={() => voteMutation.mutate({ textId: currentText.textId, vote: 'toxic' })}
              >
                <ShieldAlert className="size-4" />
                Токсичный
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="flex-1"
                disabled={voteMutation.isPending || Boolean(submittedVote)}
                onClick={() => voteMutation.mutate({ textId: currentText.textId, vote: 'nonToxic' })}
              >
                <ShieldCheck className="size-4" />
                Нетоксичный
              </Button>
            </div>

            {submittedVote ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                {isAuthenticated ? (
                  <Button asChild variant="outline">
                    <Link to={`/texts/${currentText.textId}`}>Открыть карточку текста</Link>
                  </Button>
                ) : null}
                <Button
                  onClick={async () => {
                    setSubmittedVote(null)
                    voteMutation.reset()
                    await randomTextQuery.refetch()
                  }}
                >
                  Следующий текст
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            ) : null}

            {submittedVote && isAuthenticated ? (
              textDetailsQuery.isError ? (
                <ApiErrorPanel error={textDetailsQuery.error} title="Не удалось загрузить полную информацию о тексте" />
              ) : textDetailsQuery.data ? (
                <div className="space-y-4 rounded-[1.5rem] border border-border/70 bg-surface-soft/50 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-foreground">Анализ модели</h3>
                    </div>
                    <Badge variant={textDetailsQuery.data.lastLabel === 1 ? 'warning' : 'success'}>
                      {getVerdictLabel(textDetailsQuery.data.lastLabel)}
                    </Badge>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    <InfoStatCard
                      label="Вероятность токсичности"
                      value={formatPercent(textDetailsQuery.data.lastToxicProbability)}
                      icon={<BarChart3 className="size-5" />}
                      tooltip="Это оценка модели: насколько, по мнению модели, текст похож на токсичный."
                    />
                    <InfoStatCard
                      label="Мнение сообщества"
                      value={formatPercent(
                        textDetailsQuery.data.votesToxic /
                          Math.max(1, textDetailsQuery.data.votesToxic + textDetailsQuery.data.votesNonToxic),
                      )}
                      icon={<ShieldAlert className="size-5" />}
                      tooltip="Показывает долю голосов за токсичность среди всех пользовательских оценок этого текста."
                    />
                    <InfoStatCard
                      label="Версия модели"
                      value={textDetailsQuery.data.model.modelVersion}
                      icon={<Database className="size-5" />}
                      tooltip="Версия модели, которая использовалась для последнего анализа этого текста."
                    />
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <DetailTile label="Создан" value={formatDateTime(textDetailsQuery.data.createdAt)} />
                    <DetailTile
                      label="Последняя активность"
                      value={`${formatDateTime(textDetailsQuery.data.lastSeenAt)} (${formatRelativeTime(textDetailsQuery.data.lastSeenAt)})`}
                      icon={<Clock3 className="size-4" />}
                    />
                  </div>
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="h-28 rounded-[1.25rem] bg-secondary/70" />
                  <div className="h-28 rounded-[1.25rem] bg-secondary/70" />
                  <div className="h-28 rounded-[1.25rem] bg-secondary/70" />
                  <div className="h-28 rounded-[1.25rem] bg-secondary/70" />
                </div>
              )
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function DetailTile({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
      <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{label}</div>
      <div className="mt-2 flex items-center gap-2 text-sm font-medium text-foreground">
        {icon}
        <span>{value}</span>
      </div>
    </div>
  )
}

function InfoStatCard({
  label,
  value,
  icon,
  tooltip,
}: {
  label: string
  value: string
  icon?: ReactNode
  tooltip: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="cursor-help">
          <StatCard label={label} value={value} icon={icon} />
        </div>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  )
}
