import { cn } from '@/shared/lib/cn'
import { Badge } from '@/shared/ui/badge'

interface PageIntroProps {
  eyebrow: string
  title: string
  description: string
  className?: string
}

export function PageIntro({ eyebrow, title, description, className }: PageIntroProps) {
  return (
    <section className={cn('space-y-3', className)}>
      <Badge variant="secondary" className="w-fit text-primary">
        {eyebrow}
      </Badge>
      <div className="space-y-2">
        <h1 className="max-w-3xl text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          {title}
        </h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
          {description}
        </p>
      </div>
    </section>
  )
}
