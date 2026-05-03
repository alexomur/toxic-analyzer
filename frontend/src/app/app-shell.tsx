import { Activity, BarChart3, LogOut, Moon, ShieldCheck, Sun, UserRound } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTheme } from '@/app/theme-provider'
import { useAuth } from '@/features/auth/auth-context'
import { cn } from '@/shared/lib/cn'
import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

const navigation = [
  { to: '/', label: 'Проверка текста' },
  { to: '/batch', label: 'Проверка набора' },
  { to: '/vote', label: 'Разметка данных' },
]

export function AppShell() {
  const { isAuthenticated, logout, session } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,rgba(13,148,136,0.08),transparent_28%),radial-gradient(circle_at_right,rgba(249,115,22,0.05),transparent_20%)] dark:bg-[radial-gradient(circle_at_top,rgba(45,212,191,0.08),transparent_24%),radial-gradient(circle_at_right,rgba(251,146,60,0.05),transparent_16%)]" />
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-xl">
        <div className="container flex flex-col gap-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center justify-between gap-4">
            <NavLink to="/" className="flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
                <ShieldCheck className="size-5" />
              </div>
              <div>
                <div className="text-base font-semibold tracking-tight">Toxic Analyzer</div>
                <div className="text-xs tracking-[0.08em] text-muted-foreground">Проверка токсичности русскоязычных комментариев</div>
              </div>
            </NavLink>
          </div>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-end">
            <nav className="flex gap-2 overflow-x-auto whitespace-nowrap">
              {navigation.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'rounded-full px-4 py-2 text-sm font-semibold transition whitespace-nowrap',
                      isActive ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-card/80 hover:text-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <Button variant="outline" size="icon" onClick={toggleTheme} className="bg-card/70" aria-label="Переключить тему">
              {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>

            {isAuthenticated && session ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="justify-between gap-3 bg-card/70">
                    <span className="flex items-center gap-2">
                      <span className="flex size-8 items-center justify-center rounded-full bg-secondary text-primary">
                        <UserRound className="size-4" />
                      </span>
                      <span className="max-w-[180px] truncate text-left">
                        {session.name ?? session.email ?? 'Пользователь'}
                      </span>
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Профиль</DropdownMenuLabel>
                  <DropdownMenuItem className="flex-col items-start gap-1">
                    <span className="font-medium text-foreground">{session.email ?? session.subjectId}</span>
                    <span className="text-xs text-muted-foreground">{session.name ?? 'Авторизованная сессия'}</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => {
                      navigate('/vote')
                    }}
                  >
                    <Activity className="mr-2 size-4" />
                    Открыть разметку
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      navigate('/batch')
                    }}
                  >
                    <BarChart3 className="mr-2 size-4" />
                    Открыть проверку набора
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={async () => {
                      await logout()
                      toast.success('Вы вышли из аккаунта.')
                      navigate('/')
                    }}
                  >
                    <LogOut className="mr-2 size-4" />
                    Выйти
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <Button variant="outline" onClick={() => navigate('/login')} className="bg-card/70">
                Войти
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="container py-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-border/70 py-6">
        <div className="container grid gap-4 text-sm lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)_minmax(0,0.8fr)]">
          <div className="space-y-2">
            <div className="font-semibold text-foreground">Toxic Analyzer</div>
            <p className="text-muted-foreground">
              Проверка токсичности русскоязычных комментариев, сообщений и отзывов в одном рабочем интерфейсе.
            </p>
          </div>
          <div className="space-y-2">
            <div className="font-semibold text-foreground">Разделы</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
              <button type="button" onClick={() => navigate('/')} className="transition hover:text-foreground">
                Проверка текста
              </button>
              <button type="button" onClick={() => navigate('/batch')} className="transition hover:text-foreground">
                Проверка набора
              </button>
              <button type="button" onClick={() => navigate('/vote')} className="transition hover:text-foreground">
                Разметка данных
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <div className="font-semibold text-foreground">Доступ</div>
            <p className="text-muted-foreground">
              Без входа доступна проверка одного текста. Проверка набора, разметка и карточки текстов открываются после авторизации.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
