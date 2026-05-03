import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '@/features/auth/auth-context'
import { ApiErrorPanel } from '@/shared/ui/api-error-panel'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { PageIntro } from '@/shared/ui/page-intro'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs'

type AuthMode = 'login' | 'register'

export function AuthPage() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const mode = (location.pathname === '/register' ? 'register' : 'login') as AuthMode
  const redirect = searchParams.get('redirect') || '/'
  const navigate = useNavigate()
  const { isAuthenticated, login, register } = useAuth()
  const [error, setError] = useState<unknown>(null)
  const [loginForm, setLoginForm] = useState({ email: '', password: '' })
  const [registerForm, setRegisterForm] = useState({ username: '', email: '', password: '' })
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (isAuthenticated) {
    return <Navigate to={redirect} replace />
  }

  return (
    <div className="mx-auto grid w-full max-w-[560px] gap-6">
      <Card className="border-border/70">
        <CardContent className="p-8">
          <Tabs
            value={mode}
            onValueChange={(nextValue) => {
              const nextSearchParams = new URLSearchParams(searchParams)
              const redirectValue = nextSearchParams.get('redirect')
              const search = redirectValue ? `?redirect=${encodeURIComponent(redirectValue)}` : ''
              navigate(`${nextValue === 'register' ? '/register' : '/login'}${search}`, { replace: true })
              setError(null)
            }}
          >
            <div className="space-y-4">
              <PageIntro
                eyebrow="Аккаунт"
                title={mode === 'login' ? 'Войдите в аккаунт' : 'Создайте аккаунт'}
                description="После входа будут доступны проверка набора, разметка данных и карточки сохранённых текстов."
              />
              <TabsList>
                <TabsTrigger value="login">Вход</TabsTrigger>
                <TabsTrigger value="register">Регистрация</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="login">
              <form
                className="space-y-5"
                onSubmit={async (event) => {
                  event.preventDefault()
                  setError(null)
                  setIsSubmitting(true)

                  try {
                    await login(loginForm)
                    toast.success('Вы вошли в аккаунт.')
                    navigate(redirect, { replace: true })
                  } catch (nextError) {
                    setError(nextError)
                  } finally {
                    setIsSubmitting(false)
                  }
                }}
              >
                <div className="space-y-2">
                  <Label htmlFor="login-email">Email</Label>
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="name@example.com"
                    value={loginForm.email}
                    onChange={(event) => setLoginForm((current) => ({ ...current, email: event.target.value }))}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="login-password">Пароль</Label>
                  <Input
                    id="login-password"
                    type="password"
                    placeholder="Введите пароль"
                    value={loginForm.password}
                    onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))}
                    required
                  />
                </div>
                {error ? <ApiErrorPanel error={error} title="Не удалось войти" /> : null}
                <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                  Продолжить
                  <ArrowRight className="size-4" />
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register">
              <form
                className="space-y-5"
                onSubmit={async (event) => {
                  event.preventDefault()
                  setError(null)
                  setIsSubmitting(true)

                  try {
                    await register({
                      ...registerForm,
                      username: registerForm.username || undefined,
                    })
                    toast.success('Аккаунт создан.')
                    navigate(redirect, { replace: true })
                  } catch (nextError) {
                    setError(nextError)
                  } finally {
                    setIsSubmitting(false)
                  }
                }}
              >
                <div className="space-y-2">
                  <Label htmlFor="register-username">Имя</Label>
                  <Input
                    id="register-username"
                    placeholder="Необязательно"
                    value={registerForm.username}
                    onChange={(event) => setRegisterForm((current) => ({ ...current, username: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="register-email">Email</Label>
                  <Input
                    id="register-email"
                    type="email"
                    placeholder="name@example.com"
                    value={registerForm.email}
                    onChange={(event) => setRegisterForm((current) => ({ ...current, email: event.target.value }))}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="register-password">Пароль</Label>
                  <Input
                    id="register-password"
                    type="password"
                    placeholder="Придумайте пароль"
                    value={registerForm.password}
                    onChange={(event) => setRegisterForm((current) => ({ ...current, password: event.target.value }))}
                    required
                  />
                </div>
                {error ? <ApiErrorPanel error={error} title="Не удалось зарегистрироваться" /> : null}
                <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                  Создать аккаунт
                  <ArrowRight className="size-4" />
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
