import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { Card, CardContent } from '@/shared/ui/card'

interface StatCardProps {
  label: string
  value: string
  hint?: string
  icon?: ReactNode
  className?: string
}

export function StatCard({ label, value, hint, icon, className }: StatCardProps) {
  return (
    <Card className={cn('border-border/70 bg-card/90', className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.02em] text-muted-foreground">{label}</p>
            <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">{value}</p>
            {hint ? <p className="mt-2 text-sm text-muted-foreground">{hint}</p> : null}
          </div>
          {icon ? <div className="rounded-2xl bg-secondary/70 p-3 text-primary">{icon}</div> : null}
        </div>
      </CardContent>
    </Card>
  )
}
