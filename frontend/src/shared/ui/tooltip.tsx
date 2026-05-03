import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from '@/shared/lib/cn'

export const TooltipProvider = TooltipPrimitive.Provider
export const Tooltip = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export function TooltipContent({ className, sideOffset = 8, ...props }: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          'z-50 max-w-xs rounded-2xl bg-foreground px-3 py-2 text-xs font-medium text-background shadow-panel',
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  )
}
