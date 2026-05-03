import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/shared/lib/cn'

const alertVariants = cva('relative w-full rounded-[1.25rem] border px-4 py-4 text-sm', {
  variants: {
    variant: {
      default: 'border-border bg-card/90 text-foreground',
      warning: 'border-accent/20 bg-accent/10 text-foreground',
      danger: 'border-danger/20 bg-danger/10 text-foreground',
      success: 'border-success/20 bg-success/10 text-foreground',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
})

export function Alert({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn('mb-1 font-semibold leading-none tracking-tight', className)} {...props} />
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('text-sm leading-6 text-muted-foreground', className)} {...props} />
}
