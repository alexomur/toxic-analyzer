import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import { App } from '@/app/App'
import { ThemeProvider, useTheme } from '@/app/theme-provider'
import { AuthProvider } from '@/features/auth/auth-context'
import { TooltipProvider } from '@/shared/ui/tooltip'

export function Providers() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider delayDuration={120}>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
            <ThemedToaster />
          </AuthProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

function ThemedToaster() {
  const { theme } = useTheme()

  return (
    <Toaster
      theme={theme}
      position="top-right"
      toastOptions={{
        classNames: {
          toast: '!border-border/70 !bg-card !text-foreground !shadow-panel',
          title: '!text-foreground',
          description: '!text-muted-foreground',
          actionButton: '!bg-primary !text-primary-foreground',
          cancelButton: '!bg-secondary !text-secondary-foreground',
          success: '!border-success/25',
          error: '!border-danger/25',
          warning: '!border-accent/25',
          info: '!border-border/70',
        },
      }}
    />
  )
}
