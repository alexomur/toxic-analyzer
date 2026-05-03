import { getScoreBand, scoreBands } from '@/shared/lib/score'
import type { BatchEnrichedItem } from '@/features/toxicity/toxicity-api'
import type { BatchAnalyzeRequestItem } from '@/features/toxicity/toxicity-types'

export interface BatchHistogramBucket {
  key: string
  label: string
  min: number
  max: number
  count: number
}

export interface BatchBandBreakdown {
  key: string
  label: string
  description: string
  min: number
  max: number
  count: number
}

export interface BatchDashboard {
  total: number
  toxicCount: number
  nonToxicCount: number
  averageToxicProbability: number
  histogram: BatchHistogramBucket[]
  bands: BatchBandBreakdown[]
  topToxic: BatchEnrichedItem[]
}

export interface RangeFilter {
  key: string
  label: string
  min: number
  max: number
}

export function normalizeLinesToItems(rawText: string) {
  return rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text, index) => ({
      clientItemId: `line-${index + 1}`,
      text,
    })) satisfies BatchAnalyzeRequestItem[]
}

export function buildHistogram(items: BatchEnrichedItem[]) {
  const buckets = Array.from({ length: 10 }, (_, index) => {
    const min = index / 10
    const max = index === 9 ? 1.01 : (index + 1) / 10
    return {
      key: `bucket-${index}`,
      label: `${min.toFixed(1)}-${Math.min(1, max).toFixed(1)}`,
      min,
      max,
      count: 0,
    }
  })

  items.forEach((item) => {
    const bucketIndex = Math.min(9, Math.floor(item.toxicProbability * 10))
    buckets[bucketIndex].count += 1
  })

  return buckets
}

export function buildBatchDashboard(items: BatchEnrichedItem[]): BatchDashboard {
  const toxicCount = items.filter((item) => item.label === 1).length
  const total = items.length
  const averageToxicProbability =
    total === 0 ? 0 : items.reduce((sum, item) => sum + item.toxicProbability, 0) / total

  const bandBreakdown = scoreBands.map((band) => ({
    key: band.key,
    label: band.label,
    description: band.description,
    min: band.min,
    max: band.max,
    count: items.filter((item) => item.toxicProbability >= band.min && item.toxicProbability < band.max).length,
  }))

  return {
    total,
    toxicCount,
    nonToxicCount: total - toxicCount,
    averageToxicProbability,
    histogram: buildHistogram(items),
    bands: bandBreakdown,
    topToxic: [...items].sort((left, right) => right.toxicProbability - left.toxicProbability).slice(0, 6),
  }
}

export function filterItemsByRange(items: BatchEnrichedItem[], range: RangeFilter | null) {
  if (!range) {
    return items
  }

  return items.filter((item) => item.toxicProbability >= range.min && item.toxicProbability < range.max)
}

export function describeItemBand(score: number) {
  return getScoreBand(score)
}
