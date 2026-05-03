import * as SeparatorPrimitive from '@radix-ui/react-separator'
import { cn } from '@/shared/lib/cn'

export function Separator({ className, orientation = 'horizontal', ...props }: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      className={cn(
        'shrink-0 bg-border/80',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
      decorative
      orientation={orientation}
      {...props}
    />
  )
}
