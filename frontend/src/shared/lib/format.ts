import { format, formatDistanceToNowStrict } from 'date-fns'

export function formatPercent(value: number, maximumFractionDigits = 1) {
  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits,
  }).format(value)
}

export function formatScore(value: number, maximumFractionDigits = 3) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  }).format(value)
}

export function formatCompactNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

export function formatDateTime(value: string | Date) {
  return format(new Date(value), 'MMM d, yyyy HH:mm')
}

export function formatRelativeTime(value: string | Date) {
  return formatDistanceToNowStrict(new Date(value), { addSuffix: true })
}
