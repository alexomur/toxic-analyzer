export type VerdictTone = 'safe' | 'warning'

export interface ScoreBand {
  key: string
  label: string
  min: number
  max: number
  description: string
}

export const scoreBands: ScoreBand[] = [
  {
    key: 'minimal',
    label: 'Минимальный риск',
    min: 0,
    max: 0.2,
    description: 'Почти нейтральный текст без заметных признаков агрессии.',
  },
  {
    key: 'low',
    label: 'Низкий риск',
    min: 0.2,
    max: 0.4,
    description: 'Есть напряжённые формулировки, но уверенность в токсичности низкая.',
  },
  {
    key: 'moderate',
    label: 'Средний риск',
    min: 0.4,
    max: 0.6,
    description: 'Сигналы смешанные: такой текст стоит проверить внимательнее.',
  },
  {
    key: 'high',
    label: 'Высокий риск',
    min: 0.6,
    max: 0.8,
    description: 'Текст с высокой вероятностью содержит агрессию или оскорбления.',
  },
  {
    key: 'critical',
    label: 'Критический риск',
    min: 0.8,
    max: 1.01,
    description: 'Очень высокая уверенность в токсичности. Такой текст требует приоритета.',
  },
]

export function getVerdictLabel(label: number) {
  return label === 1 ? 'Токсичный' : 'Нетоксичный'
}

export function getVerdictTone(label: number): VerdictTone {
  return label === 1 ? 'warning' : 'safe'
}

export function getScoreBand(score: number) {
  return scoreBands.find((band) => score >= band.min && score < band.max) ?? scoreBands[scoreBands.length - 1]
}
