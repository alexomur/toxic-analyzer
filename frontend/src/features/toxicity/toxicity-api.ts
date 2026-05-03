import { apiRequest } from '@/shared/api/client'
import { chunk } from '@/shared/lib/chunk'
import type {
  AnalyzeBatchItemResponse,
  AnalyzeBatchResponse,
  AnalyzeTextResponse,
  BatchAnalyzeRequestItem,
  RandomTextResponse,
  TextDetailsResponse,
  VoteKind,
} from '@/features/toxicity/toxicity-types'

export const toxicityQueryKeys = {
  randomText: ['toxicity', 'random-text'] as const,
  textDetails: (textId: string) => ['toxicity', 'text-details', textId] as const,
}

export function analyzeText(text: string) {
  return apiRequest<AnalyzeTextResponse>('/api/v1/toxicity/analyze', {
    method: 'POST',
    body: {
      text,
      reportLevel: 'full',
    },
  })
}

export function analyzeBatch(items: BatchAnalyzeRequestItem[]) {
  return apiRequest<AnalyzeBatchResponse>('/api/v1/toxicity/analyze-batch', {
    method: 'POST',
    body: { items },
  })
}

export function getRandomText() {
  return apiRequest<RandomTextResponse>('/api/v1/toxicity/texts/random')
}

export function voteForText(textId: string, vote: VoteKind) {
  return apiRequest<void>(`/api/v1/toxicity/texts/${textId}/vote`, {
    method: 'POST',
    body: { vote },
  })
}

export function getTextDetails(textId: string) {
  return apiRequest<TextDetailsResponse>(`/api/v1/toxicity/texts/${textId}`)
}

export interface BatchProgressState {
  completedItems: number
  totalItems: number
  currentChunk: number
  totalChunks: number
}

export interface BatchEnrichedItem extends AnalyzeBatchItemResponse {
  sourceIndex: number
  text: string
}

export interface BatchRunResult {
  batchId: string
  createdAt: string
  items: BatchEnrichedItem[]
}

export async function analyzeBatchInChunks(
  items: BatchAnalyzeRequestItem[],
  onProgress?: (progress: BatchProgressState) => void,
): Promise<BatchRunResult> {
  const chunks = chunk(items, 100)
  const mergedItems: BatchEnrichedItem[] = []
  let batchId = ''
  let createdAt = new Date().toISOString()
  let completedItems = 0

  for (const [chunkIndex, batchChunk] of chunks.entries()) {
    const response = await analyzeBatch(batchChunk)
    batchId ||= response.batchId
    createdAt = response.createdAt

    response.items.forEach((item, itemIndex) => {
      const sourceItem = batchChunk[itemIndex]
      mergedItems.push({
        ...item,
        sourceIndex: completedItems + itemIndex,
        text: sourceItem.text,
      })
    })

    completedItems += batchChunk.length
    onProgress?.({
      completedItems,
      totalItems: items.length,
      currentChunk: chunkIndex + 1,
      totalChunks: chunks.length,
    })
  }

  return {
    batchId,
    createdAt,
    items: mergedItems,
  }
}
