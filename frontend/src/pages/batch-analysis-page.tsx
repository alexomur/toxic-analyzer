import { startTransition, useDeferredValue, useMemo, useState, type ReactNode } from 'react'
import { useMutation } from '@tanstack/react-query'
import Papa from 'papaparse'
import {
  BarChart3,
  FilterX,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Search,
  Sparkles,
  Upload,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { toast } from 'sonner'
import { buildBatchDashboard, describeItemBand, filterItemsByRange, normalizeLinesToItems, type RangeFilter } from '@/features/batch/batch-utils'
import { analyzeBatchInChunks, type BatchEnrichedItem, type BatchProgressState } from '@/features/toxicity/toxicity-api'
import type { BatchAnalyzeRequestItem } from '@/features/toxicity/toxicity-types'
import { formatPercent, formatScore } from '@/shared/lib/format'
import { getVerdictLabel } from '@/shared/lib/score'
import { Alert, AlertDescription, AlertTitle } from '@/shared/ui/alert'
import {
  AlertDialog,
  AlertDialogActionButton,
  AlertDialogCancelButton,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/ui/alert-dialog'
import { ApiErrorPanel } from '@/shared/ui/api-error-panel'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/shared/ui/dialog'
import { EmptyState } from '@/shared/ui/empty-state'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { PageIntro } from '@/shared/ui/page-intro'
import { Progress } from '@/shared/ui/progress'
import { ScrollArea } from '@/shared/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'
import { StatCard } from '@/shared/ui/stat-card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import { Textarea } from '@/shared/ui/textarea'

function formatTooltipValue(value: number | string | readonly (number | string)[] | undefined) {
  const normalizedValue = Array.isArray(value) ? value[0] : value
  return [Number(normalizedValue ?? 0), 'Текстов'] as [number, string]
}

type SourceMode = 'manual' | 'file'
type LabelFilter = 'all' | 'toxic' | 'nonToxic'
type SortDirection = 'desc' | 'asc'

interface CsvRecord {
  [key: string]: string
}

export function BatchAnalysisPage() {
  const [sourceMode, setSourceMode] = useState<SourceMode>('manual')
  const [manualText, setManualText] = useState(
    'Спасибо за полезный ответ.\nТы полный идиот, лучше бы молчал.\nОбсуждение становится жёстким, но в нём всё ещё есть конструктивная часть.',
  )
  const [importError, setImportError] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileKind, setFileKind] = useState<'txt' | 'csv' | null>(null)
  const [txtItems, setTxtItems] = useState<BatchAnalyzeRequestItem[]>([])
  const [csvRows, setCsvRows] = useState<CsvRecord[]>([])
  const [csvHeaders, setCsvHeaders] = useState<string[]>([])
  const [textColumn, setTextColumn] = useState<string>('')
  const [idColumn, setIdColumn] = useState<string>('__none__')
  const [progress, setProgress] = useState<BatchProgressState | null>(null)
  const [rangeFilter, setRangeFilter] = useState<RangeFilter | null>(null)
  const [labelFilter, setLabelFilter] = useState<LabelFilter>('all')
  const [search, setSearch] = useState('')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const deferredSearch = useDeferredValue(search.trim().toLowerCase())

  const preparedItems = useMemo(() => {
    if (sourceMode === 'manual') {
      return normalizeLinesToItems(manualText)
    }

    if (fileKind === 'txt') {
      return txtItems
    }

    if (fileKind === 'csv' && textColumn) {
      return csvRows
        .map((row, index) => {
          const text = (row[textColumn] ?? '').trim()
          const rawId = idColumn !== '__none__' ? (row[idColumn] ?? '').trim() : ''
          return {
            clientItemId: rawId || `row-${index + 1}`,
            text,
          }
        })
        .filter((item) => item.text.length > 0)
    }

    return []
  }, [csvRows, fileKind, idColumn, manualText, sourceMode, textColumn, txtItems])

  const analyzeMutation = useMutation({
    mutationFn: async (items: BatchAnalyzeRequestItem[]) => {
      setProgress({
        completedItems: 0,
        totalItems: items.length,
        currentChunk: 0,
        totalChunks: Math.max(1, Math.ceil(items.length / 100)),
      })
      return analyzeBatchInChunks(items, setProgress)
    },
    onSuccess: () => {
      toast.success('Пакетный анализ завершён.')
    },
  })

  const dashboard = useMemo(
    () => (analyzeMutation.data ? buildBatchDashboard(analyzeMutation.data.items) : null),
    [analyzeMutation.data],
  )

  const filteredItems = useMemo(() => {
    if (!analyzeMutation.data) {
      return []
    }

    const rangeFiltered = filterItemsByRange(analyzeMutation.data.items, rangeFilter)
    const labelFiltered = rangeFiltered.filter((item) => {
      if (labelFilter === 'all') {
        return true
      }

      return labelFilter === 'toxic' ? item.label === 1 : item.label === 0
    })
    const searchFiltered = labelFiltered.filter((item) => {
      if (!deferredSearch) {
        return true
      }

      return (
        item.text.toLowerCase().includes(deferredSearch) ||
        (item.clientItemId ?? '').toLowerCase().includes(deferredSearch)
      )
    })

    return [...searchFiltered].sort((left, right) =>
      sortDirection === 'desc'
        ? right.toxicProbability - left.toxicProbability
        : left.toxicProbability - right.toxicProbability,
    )
  }, [analyzeMutation.data, deferredSearch, labelFilter, rangeFilter, sortDirection])

  async function handleFileSelection(file: File) {
    setImportError(null)
    setFileName(file.name)
    const extension = file.name.split('.').pop()?.toLowerCase()

    if (extension === 'txt') {
      const fileContent = await file.text()
      setFileKind('txt')
      setTxtItems(normalizeLinesToItems(fileContent))
      setCsvRows([])
      setCsvHeaders([])
      setTextColumn('')
      setIdColumn('__none__')
      return
    }

    if (extension === 'csv') {
      Papa.parse<CsvRecord>(file, {
        header: true,
        skipEmptyLines: 'greedy',
        complete: (results) => {
          const headers = results.meta.fields ?? []

          if (headers.length === 0) {
            setImportError('CSV-файл прочитан, но строка заголовков не найдена.')
            return
          }

          setFileKind('csv')
          setTxtItems([])
          setCsvHeaders(headers)
          setCsvRows(results.data.filter((row) => Object.values(row).some((value) => value?.trim())))
          setTextColumn(headers[0] ?? '')
          setIdColumn('__none__')
        },
        error: (error) => {
          setImportError(error.message)
        },
      })
      return
    }

    setImportError('Поддерживаются только файлы .txt и .csv.')
  }

  const activeFilterLabel = rangeFilter?.label ?? (labelFilter !== 'all' ? (labelFilter === 'toxic' ? 'Только токсичные' : 'Только нетоксичные') : '')

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.96fr)_minmax(420px,1.04fr)]">
        <Card className="border-border/70">
          <CardHeader className="space-y-4">
            <PageIntro
              eyebrow="Проверка набора сообщений"
              title="Загрузите список текстов и быстро найдите самые рискованные фрагменты"
              description="Поддерживается ручной ввод, TXT и CSV. После запуска вы увидите распределение оценок, сводные показатели и таблицу с поиском."
            />
            <div className="grid gap-3 sm:grid-cols-3">
              <PayloadHint icon={<Upload className="size-4" />} label="Источник" value="Ввод или файл" />
              <PayloadHint icon={<FileSpreadsheet className="size-4" />} label="Форматы" value="TXT и CSV" />
              <PayloadHint icon={<BarChart3 className="size-4" />} label="На выходе" value="Распределение и таблица" />
            </div>
            <div className="border-t border-border/70" />
            <CardTitle>Подготовьте набор</CardTitle>
            <CardDescription>
              Вставьте тексты вручную или загрузите файл, проверьте предварительный просмотр и запустите проверку.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <Tabs value={sourceMode} onValueChange={(value) => setSourceMode(value as SourceMode)}>
              <TabsList>
                <TabsTrigger value="manual">Вставить тексты</TabsTrigger>
                <TabsTrigger value="file">Загрузить файл</TabsTrigger>
              </TabsList>

              <TabsContent value="manual" className="space-y-4">
                <Label htmlFor="manual-batch-text">Один текст на строку</Label>
                <Textarea
                  id="manual-batch-text"
                  className="min-h-[280px]"
                  value={manualText}
                  onChange={(event) => setManualText(event.target.value)}
                  placeholder="Вставьте по одному комментарию или сообщению на каждую строку."
                />
              </TabsContent>

              <TabsContent value="file" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="batch-file">Загрузите файл .txt или .csv</Label>
                  <Input
                    id="batch-file"
                    type="file"
                    accept=".txt,.csv,text/plain,text/csv"
                    onChange={async (event) => {
                      const file = event.target.files?.[0]
                      if (!file) {
                        return
                      }

                      await handleFileSelection(file)
                    }}
                  />
                </div>

                {fileName ? (
                  <Alert variant="default">
                    <AlertTitle>{fileName}</AlertTitle>
                    <AlertDescription>
                      {fileKind === 'csv'
                        ? 'Выберите колонку с текстом и, при необходимости, колонку с внешним идентификатором.'
                        : 'Каждая непустая строка будет обработана как отдельный текст.'}
                    </AlertDescription>
                  </Alert>
                ) : null}

                {fileKind === 'csv' && csvHeaders.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Колонка с текстом</Label>
                      <Select value={textColumn} onValueChange={setTextColumn}>
                        <SelectTrigger>
                          <SelectValue placeholder="Выберите колонку" />
                        </SelectTrigger>
                        <SelectContent>
                          {csvHeaders.map((header) => (
                            <SelectItem key={header} value={header}>
                              {header}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Колонка с идентификатором</Label>
                      <Select value={idColumn} onValueChange={setIdColumn}>
                        <SelectTrigger>
                          <SelectValue placeholder="Необязательно" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__">Не использовать</SelectItem>
                          {csvHeaders.map((header) => (
                            <SelectItem key={header} value={header}>
                              {header}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                ) : null}
              </TabsContent>
            </Tabs>

            {importError ? <ApiErrorPanel error={new Error(importError)} title="Не удалось подготовить данные" /> : null}

            <div className="rounded-[1.5rem] border border-border/70 bg-surface-soft p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">Готово к запуску</div>
                  <div className="mt-2 text-2xl font-semibold text-foreground">{preparedItems.length} текстов</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="outline" disabled={preparedItems.length === 0}>
                        Предпросмотр
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Предпросмотр набора</DialogTitle>
                        <DialogDescription>Проверьте тексты перед запуском проверки.</DialogDescription>
                      </DialogHeader>
                      <ScrollArea className="h-[420px]">
                        <div className="space-y-3 pr-4">
                          {preparedItems.map((item, index) => (
                            <div key={`${item.clientItemId ?? index}-${item.text}`} className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
                              <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">
                                {item.clientItemId ?? `item-${index + 1}`}
                              </div>
                              <div className="mt-2 text-sm leading-6 text-foreground">{item.text}</div>
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </DialogContent>
                  </Dialog>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="ghost" disabled={preparedItems.length === 0}>
                        Очистить
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Очистить текущий набор?</AlertDialogTitle>
                        <AlertDialogDescription>
                          Текущий ввод и предварительный просмотр будут сброшены.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancelButton>Отмена</AlertDialogCancelButton>
                        <AlertDialogActionButton
                          onClick={() => {
                            setManualText('')
                            setFileName(null)
                            setFileKind(null)
                            setTxtItems([])
                            setCsvRows([])
                            setCsvHeaders([])
                            setTextColumn('')
                            setIdColumn('__none__')
                          }}
                        >
                          Очистить
                        </AlertDialogActionButton>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <PayloadHint
                  icon={sourceMode === 'manual' ? <FileText className="size-4" /> : <Upload className="size-4" />}
                  label="Источник данных"
                  value={sourceMode === 'manual' ? 'Ручной ввод' : fileKind === 'csv' ? 'CSV-файл' : fileKind === 'txt' ? 'TXT-файл' : 'Файл не выбран'}
                />
                <PayloadHint icon={<FileSpreadsheet className="size-4" />} label="Объём" value={preparedItems.length > 0 ? `${preparedItems.length} текстов` : 'Набор пока пуст'} />
              </div>
            </div>

            {preparedItems.length > 0 ? (
              <div className="space-y-3">
                <div className="text-sm font-semibold text-foreground">Первые строки</div>
                <div className="space-y-3">
                  {preparedItems.slice(0, 5).map((item, index) => (
                    <div key={`${item.clientItemId ?? index}-${item.text}`} className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
                      <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{item.clientItemId ?? `item-${index + 1}`}</div>
                      <div className="mt-2 line-clamp-2 text-sm leading-6 text-foreground">{item.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {analyzeMutation.isError ? <ApiErrorPanel error={analyzeMutation.error} title="Не удалось выполнить пакетный анализ" /> : null}

            <div className="space-y-4">
              {progress ? (
                <div className="space-y-2 rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <div className="font-medium text-foreground">
                      Часть {progress.currentChunk} из {progress.totalChunks}
                    </div>
                    <div className="text-muted-foreground">
                      {progress.completedItems} / {progress.totalItems} текстов
                    </div>
                  </div>
                  <Progress value={(progress.completedItems / Math.max(progress.totalItems, 1)) * 100} />
                </div>
              ) : null}
              <Button
                size="lg"
                className="w-full"
                disabled={preparedItems.length === 0 || analyzeMutation.isPending}
                onClick={() => {
                  startTransition(() => {
                    setRangeFilter(null)
                    setLabelFilter('all')
                    setSearch('')
                    setSortDirection('desc')
                  })
                  analyzeMutation.mutate(preparedItems)
                }}
              >
                {analyzeMutation.isPending ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" />
                    Проверяем набор
                  </>
                ) : (
                  <>
                    <Sparkles className="size-4" />
                    Запустить проверку
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {dashboard ? (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Всего" value={dashboard.total.toString()} icon={<BarChart3 className="size-5" />} />
                <StatCard label="Токсичных" value={dashboard.toxicCount.toString()} icon={<Sparkles className="size-5" />} />
                <StatCard label="Нетоксичных" value={dashboard.nonToxicCount.toString()} icon={<FilterX className="size-5" />} />
                <StatCard label="Средняя оценка" value={formatPercent(dashboard.averageToxicProbability)} icon={<Search className="size-5" />} />
              </div>

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
                <HistogramCard buckets={dashboard.histogram} activeFilter={rangeFilter} onSelect={(nextFilter) => startTransition(() => setRangeFilter(nextFilter))} />
                <LabelSplitCard toxicCount={dashboard.toxicCount} nonToxicCount={dashboard.nonToxicCount} />
              </div>

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(340px,0.92fr)]">
                <ScoreBandsCard bands={dashboard.bands} activeFilter={rangeFilter} onSelect={(nextFilter) => startTransition(() => setRangeFilter(nextFilter))} />
                <TopToxicCard items={dashboard.topToxic} />
              </div>

              <Card className="border-border/70">
                <CardHeader className="gap-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                      <CardTitle>Таблица результатов</CardTitle>
                      <CardDescription>
                        Ищите по тексту, фильтруйте выборку и сортируйте строки по вероятности токсичности.
                      </CardDescription>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <div className="relative min-w-[240px] flex-1">
                        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input className="pl-9" placeholder="Поиск по тексту или идентификатору" value={search} onChange={(event) => setSearch(event.target.value)} />
                      </div>
                      <Select value={labelFilter} onValueChange={(value) => setLabelFilter(value as LabelFilter)}>
                        <SelectTrigger className="w-[180px]">
                          <SelectValue placeholder="Фильтр по метке" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">Все тексты</SelectItem>
                          <SelectItem value="toxic">Только токсичные</SelectItem>
                          <SelectItem value="nonToxic">Только нетоксичные</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button variant="outline" onClick={() => setSortDirection((current) => (current === 'desc' ? 'asc' : 'desc'))}>
                        Сортировка: {sortDirection === 'desc' ? 'сначала высокая оценка' : 'сначала низкая оценка'}
                      </Button>
                    </div>
                  </div>
                  {activeFilterLabel ? (
                    <div className="flex items-center gap-3">
                      <Badge variant="secondary">{activeFilterLabel}</Badge>
                      <Button variant="ghost" size="sm" onClick={() => setRangeFilter(null)}>
                        Сбросить диапазон
                      </Button>
                    </div>
                  ) : null}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-sm text-muted-foreground">В текущем представлении: {filteredItems.length}</div>
                  <ResultsTable items={filteredItems} />
                </CardContent>
              </Card>
            </>
          ) : (
            <EmptyState
              icon={<BarChart3 className="size-6" />}
              title="Сводка появится после запуска проверки."
              description="Загрузите или вставьте тексты, чтобы увидеть распределение оценок, ключевые показатели и таблицу результатов."
            />
          )}
        </div>
      </div>
    </div>
  )
}

function PayloadHint({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-[1.25rem] border border-border/70 bg-surface-soft/70 p-4">
      <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.02em] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-3 text-sm font-medium text-foreground">{value}</div>
    </div>
  )
}

function HistogramCard({
  buckets,
  activeFilter,
  onSelect,
}: {
  buckets: ReturnType<typeof buildBatchDashboard>['histogram']
  activeFilter: RangeFilter | null
  onSelect: (filter: RangeFilter | null) => void
}) {
  return (
    <Card className="border-border/70">
      <CardHeader>
        <CardTitle>Распределение оценок</CardTitle>
        <CardDescription>Нажмите на диапазон, чтобы отфильтровать таблицу по этому сегменту.</CardDescription>
      </CardHeader>
      <CardContent className="h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(148, 163, 184, 0.2)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
            <RechartsTooltip cursor={{ fill: 'rgba(15, 23, 42, 0.04)' }} formatter={formatTooltipValue} />
            <Bar dataKey="count" radius={[10, 10, 0, 0]}>
              {buckets.map((bucket) => {
                const selected = activeFilter?.key === bucket.key
                return (
                  <Cell
                    key={bucket.key}
                    cursor="pointer"
                    fill={selected ? 'hsl(var(--accent))' : 'hsl(var(--chart-1))'}
                    fillOpacity={selected ? 1 : 0.78}
                    onClick={() =>
                      onSelect(
                        selected
                          ? null
                          : {
                              key: bucket.key,
                              label: bucket.label,
                              min: bucket.min,
                              max: bucket.max,
                            },
                      )
                    }
                  />
                )
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

function LabelSplitCard({ toxicCount, nonToxicCount }: { toxicCount: number; nonToxicCount: number }) {
  const data = [
    { name: 'Токсичные', value: toxicCount, color: 'hsl(var(--chart-2))' },
    { name: 'Нетоксичные', value: nonToxicCount, color: 'hsl(var(--chart-3))' },
  ]

  return (
    <Card className="border-border/70">
      <CardHeader>
        <CardTitle>Токсичные и нетоксичные</CardTitle>
        <CardDescription>Соотношение меток по всему набору.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={64} outerRadius={96} paddingAngle={4}>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <RechartsTooltip formatter={formatTooltipValue} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((entry) => (
            <div key={entry.name} className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <span className="size-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                {entry.name}
              </div>
              <div className="mt-2 text-2xl font-semibold">{entry.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function ScoreBandsCard({
  bands,
  activeFilter,
  onSelect,
}: {
  bands: ReturnType<typeof buildBatchDashboard>['bands']
  activeFilter: RangeFilter | null
  onSelect: (filter: RangeFilter | null) => void
}) {
  return (
    <Card className="border-border/70">
      <CardHeader>
        <CardTitle>Разбивка по диапазонам</CardTitle>
        <CardDescription>Более интерпретируемый взгляд на риск, чем просто сырые вероятности.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,0.92fr)_minmax(220px,1.08fr)]">
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart layout="vertical" data={bands}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(148, 163, 184, 0.2)" />
              <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
              <YAxis dataKey="label" type="category" width={110} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
              <RechartsTooltip formatter={formatTooltipValue} />
              <Bar dataKey="count" radius={[0, 10, 10, 0]}>
                {bands.map((band) => {
                  const selected = activeFilter?.key === band.key
                  return (
                    <Cell
                      key={band.key}
                      cursor="pointer"
                      fill={selected ? 'hsl(var(--accent))' : 'hsl(var(--chart-5))'}
                      fillOpacity={selected ? 1 : 0.85}
                      onClick={() =>
                        onSelect(
                          selected
                            ? null
                            : {
                                key: band.key,
                                label: band.label,
                                min: band.min,
                                max: band.max,
                              },
                        )
                      }
                    />
                  )
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-3">
          {bands.map((band) => (
            <button
              key={band.key}
              type="button"
              onClick={() =>
                onSelect(
                  activeFilter?.key === band.key
                    ? null
                    : {
                        key: band.key,
                        label: band.label,
                        min: band.min,
                        max: band.max,
                      },
                )
              }
              className={`w-full rounded-[1.25rem] border p-4 text-left transition ${
                activeFilter?.key === band.key
                  ? 'border-accent/30 bg-accent/10'
                  : 'border-border/70 bg-card/90 hover:border-primary/20'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="font-semibold text-foreground">{band.label}</div>
                <div className="font-mono text-sm text-muted-foreground">{band.count}</div>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{band.description}</p>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function TopToxicCard({ items }: { items: BatchEnrichedItem[] }) {
  return (
    <Card className="border-border/70">
      <CardHeader>
        <CardTitle>Самые токсичные тексты</CardTitle>
        <CardDescription>Тексты с наибольшей вероятностью токсичности в текущем наборе.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <div key={item.analysisId} className="rounded-[1.25rem] border border-border/70 bg-card/90 p-4">
            <div className="flex items-center justify-between gap-3">
              <Badge variant="warning">{formatPercent(item.toxicProbability)}</Badge>
              <div className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">
                {item.clientItemId ?? `row-${item.sourceIndex + 1}`}
              </div>
            </div>
            <div className="mt-3 text-sm leading-6 text-foreground">{item.text}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function ResultsTable({ items }: { items: BatchEnrichedItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="По текущим фильтрам ничего не найдено."
        description="Снимите часть фильтров или очистите поиск, чтобы расширить выборку."
      />
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Текст</TableHead>
          <TableHead>Вердикт</TableHead>
          <TableHead>Диапазон</TableHead>
          <TableHead className="text-right">Вероятность</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const band = describeItemBand(item.toxicProbability)
          return (
            <TableRow key={item.analysisId}>
              <TableCell className="font-mono text-xs text-muted-foreground">{item.clientItemId ?? `row-${item.sourceIndex + 1}`}</TableCell>
              <TableCell className="max-w-[460px]">
                <div className="line-clamp-2 leading-6">{item.text}</div>
              </TableCell>
              <TableCell>
                <Badge variant={item.label === 1 ? 'warning' : 'success'}>{getVerdictLabel(item.label)}</Badge>
              </TableCell>
              <TableCell>{band.label}</TableCell>
              <TableCell className="text-right font-mono">{formatScore(item.toxicProbability)}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
