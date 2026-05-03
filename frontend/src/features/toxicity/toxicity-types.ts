export interface ModelInfo {
  modelKey: string
  modelVersion: string
}

export interface AnalyzeTextExplanationFeature {
  name: string
  contribution: number
}

export interface AnalyzeTextExplanation {
  calibratedProbability: number
  adjustedProbability: number
  threshold: number
  features: AnalyzeTextExplanationFeature[]
}

export interface AnalyzeTextResponse {
  analysisId: string
  textId: string | null
  label: number
  toxicProbability: number
  model: ModelInfo
  reportLevel: 'summary' | 'full'
  explanation: AnalyzeTextExplanation | null
  createdAt: string
}

export interface BatchAnalyzeRequestItem {
  clientItemId?: string
  text: string
}

export interface AnalyzeBatchItemResponse {
  clientItemId: string | null
  analysisId: string
  label: number
  toxicProbability: number
  model: ModelInfo
}

export interface AnalyzeBatchResponse {
  batchId: string
  items: AnalyzeBatchItemResponse[]
  summary: {
    total: number
    toxicCount: number
    nonToxicCount: number
    averageToxicProbability: number
  }
  createdAt: string
}

export interface RandomTextResponse {
  textId: string
  text: string
}

export interface TextDetailsResponse {
  textId: string
  text: string
  textLength: number
  requestCount: number
  lastLabel: number
  lastToxicProbability: number
  model: ModelInfo
  votesToxic: number
  votesNonToxic: number
  createdAt: string
  lastSeenAt: string
}

export type VoteKind = 'toxic' | 'nonToxic'
