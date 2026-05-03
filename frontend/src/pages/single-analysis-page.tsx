import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ArrowUpRight, Info, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { analyzeText } from '@/features/toxicity/toxicity-api'
import type { AnalyzeTextExplanationFeature, AnalyzeTextResponse } from '@/features/toxicity/toxicity-types'
import { useAuth } from '@/features/auth/auth-context'
import { formatPercent, formatScore } from '@/shared/lib/format'
import { getScoreBand, getVerdictLabel, getVerdictTone } from '@/shared/lib/score'
import { ApiErrorPanel } from '@/shared/ui/api-error-panel'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { EmptyState } from '@/shared/ui/empty-state'
import { Progress } from '@/shared/ui/progress'
import { Separator } from '@/shared/ui/separator'
import { Textarea } from '@/shared/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip'

const samples = [
  {
    label: 'Спокойный',
    text: 'Я не согласен с вашим подходом, но если упростить план запуска, идея может сработать.',
  },
  {
    label: 'Резко токсичный',
    text: 'Ты ведешь себя как придурок, от тебя одни проблемы.',
  },
  {
    label: 'Пограничный',
    text: 'Меньше тупи, а то ты сегодня рассеянный.',
  },
]

export function SingleAnalysisPage() {
  const { isAuthenticated } = useAuth()
  const [text, setText] = useState(samples[0].text)
  const analyzeMutation = useMutation({
    mutationFn: analyzeText,
  })

  const result = analyzeMutation.data

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <Card className="border-border/70">
          <CardHeader className="space-y-4">
            <Badge variant="secondary" className="w-fit text-primary">
              Проверка одного комментария
            </Badge>
            <div className="space-y-3">
              <CardTitle className="text-3xl sm:text-4xl">Вставьте текст и сразу получите оценку токсичности</CardTitle>
              <CardDescription className="max-w-2xl text-sm leading-6 sm:text-base">
                Сервис показывает итоговый вердикт, вероятность токсичности и краткое объяснение, какие признаки сильнее всего повлияли на результат.
              </CardDescription>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <QuickFact label="Что проверяем" value="Комментарии и сообщения" />
              <QuickFact label="Что получаете" value="Вердикт и оценку" />
              <QuickFact label="Объяснение" value="Что повлияло на результат" />
            </div>
            <Separator />
            <div>
              <CardTitle className="text-2xl">Введите текст</CardTitle>
            </div>
            <CardDescription>
              Поддерживаются русскоязычные комментарии, отзывы и сообщения. Можно начать с одного из примеров ниже.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex flex-wrap gap-2">
              {samples.map((sample) => (
                <button
                  key={sample.label}
                  type="button"
                  className="rounded-full border border-border/80 bg-card/70 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition hover:border-primary/20 hover:text-foreground"
                  onClick={() => setText(sample.text)}
                >
                  <span className="mr-2 text-primary">{sample.label}:</span>
                  {sample.text.slice(0, 46)}...
                </button>
              ))}
            </div>
            <Textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Вставьте комментарий, сообщение или отзыв на русском языке."
              className="min-h-[260px] text-base"
            />
            {analyzeMutation.isError ? <ApiErrorPanel error={analyzeMutation.error} title="Не удалось выполнить анализ" /> : null}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-muted-foreground">Лучше всего работают цельные фразы или законченные комментарии.</div>
              <Button
                size="lg"
                onClick={() => analyzeMutation.mutate(text)}
                disabled={analyzeMutation.isPending || text.trim().length === 0}
              >
                {analyzeMutation.isPending ? 'Проверяем...' : 'Проверить текст'}
                <Sparkles className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <ResultPanel result={result} isAuthenticated={isAuthenticated} isPending={analyzeMutation.isPending} />
      </div>
    </div>
  )
}

function ResultPanel({
  result,
  isPending,
  isAuthenticated,
}: {
  result?: AnalyzeTextResponse
  isPending: boolean
  isAuthenticated: boolean
}) {
  if (isPending) {
    return (
      <Card className="overflow-hidden border-primary/10">
        <CardContent className="space-y-5 p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold tracking-[0.02em] text-muted-foreground">Идёт проверка</div>
              <div className="mt-2 text-2xl font-semibold">Готовим результат по тексту...</div>
            </div>
          </div>
          <Progress value={62} className="h-3" />
        </CardContent>
      </Card>
    )
  }

  if (!result) {
    return (
      <EmptyState
        icon={<Sparkles className="size-6" />}
        title="Результат появится после проверки."
        description="Мы покажем итоговый вердикт, оценку токсичности и короткое объяснение по ключевым признакам."
      />
    )
  }

  const band = getScoreBand(result.toxicProbability)
  const verdictTone = getVerdictTone(result.label)

  return (
    <Card className="overflow-hidden border-border/70">
      <div className="border-b border-border/70 bg-[linear-gradient(135deg,rgba(13,148,136,0.1),rgba(249,115,22,0.08))] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <Badge variant={verdictTone === 'warning' ? 'warning' : 'success'}>
              {getVerdictLabel(result.label)}
            </Badge>
            <div>
              <h2 className="text-3xl font-semibold tracking-tight text-foreground">{formatPercent(result.toxicProbability, 1)}</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">{band.description}</p>
            </div>
          </div>
          <div className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
            <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">Модель</div>
            <div className="mt-2 font-mono text-sm text-foreground">{result.model.modelKey}</div>
            <div className="text-sm text-muted-foreground">v{result.model.modelVersion}</div>
          </div>
        </div>
        <div className="mt-5">
          <Progress
            value={result.toxicProbability * 100}
            className="h-3"
            indicatorClassName={verdictTone === 'warning' ? 'bg-accent' : 'bg-success'}
          />
        </div>
      </div>

      <CardContent className="space-y-5 p-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <Metric label="Итоговая оценка" value={formatScore(result.toxicProbability)} />
          <Metric
            label="Калиброванная"
            value={result.explanation ? formatScore(result.explanation.calibratedProbability) : 'н/д'}
          />
          <Metric
            label="Скорректированная"
            value={result.explanation ? formatScore(result.explanation.adjustedProbability) : 'н/д'}
          />
        </div>
        <Separator />
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">Что сильнее всего повлияло на результат</h3>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="text-muted-foreground transition hover:text-foreground">
                  <Info className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                Чем длиннее полоса, тем заметнее вклад признака в итоговую оценку.
              </TooltipContent>
            </Tooltip>
          </div>
          {result.explanation ? <FeatureContributionList features={result.explanation.features} /> : null}
        </div>

        <div className="flex flex-wrap gap-3">
          {result.textId ? (
            isAuthenticated ? (
              <Button asChild variant="outline">
                <Link to={`/texts/${result.textId}`}>
                  Открыть карточку текста
                  <ArrowUpRight className="size-4" />
                </Link>
              </Button>
            ) : (
              <Button asChild variant="outline">
                <Link to={`/login?redirect=${encodeURIComponent(`/texts/${result.textId}`)}`}>
                  Войти, чтобы открыть карточку текста
                  <ArrowUpRight className="size-4" />
                </Link>
              </Button>
            )
          ) : null}
          <Button asChild variant="ghost">
            <Link to="/vote">Перейти к разметке</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-surface-soft p-4">
      <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{label}</div>
      <div className="mt-3 font-mono text-2xl font-semibold text-foreground">{value}</div>
    </div>
  )
}

function QuickFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.1rem] border border-border/70 bg-surface-soft/70 p-4">
      <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-base font-semibold text-foreground">{value}</div>
    </div>
  )
}

function FeatureContributionList({ features }: { features: AnalyzeTextExplanationFeature[] }) {
  const sortedFeatures = useMemo(
    () =>
      [...features]
        .sort((left, right) => Math.abs(right.contribution) - Math.abs(left.contribution))
        .slice(0, 8),
    [features],
  )

  const maxContribution = sortedFeatures.reduce((max, feature) => Math.max(max, Math.abs(feature.contribution)), 0.0001)

  return (
    <div className="space-y-3">
      {sortedFeatures.map((feature) => {
        const width = `${(Math.abs(feature.contribution) / maxContribution) * 100}%`
        const positive = feature.contribution >= 0

        return (
          <div key={`${feature.name}-${feature.contribution}`} className="space-y-2 rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="font-medium text-foreground">{feature.name}</div>
              <div className="font-mono text-sm text-muted-foreground">{formatScore(feature.contribution)}</div>
            </div>
            <div className="h-2.5 rounded-full bg-secondary">
              <div className={`h-full rounded-full ${positive ? 'bg-accent' : 'bg-primary'}`} style={{ width }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
