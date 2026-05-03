import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('rounded-[1.75rem] border border-dashed border-border/80 bg-surface-soft/90 p-8 text-center', className)}>
      {icon ? <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-full bg-secondary/80 text-primary">{icon}</div> : null}
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  )
}
