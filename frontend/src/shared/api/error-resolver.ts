import type { ProblemDetails, ProblemDetailsErrorItem } from '@/shared/api/types'

interface ResolvedProblemError {
  field: string
  label: string
  message: string
}

const problemCodeMessages: Record<string, string> = {
  email_already_registered: 'Пользователь с таким email уже зарегистрирован.',
}

const fieldLabels: Record<string, string> = {
  email: 'Email',
  password: 'Пароль',
  text: 'Текст',
  items: 'Список',
  vote: 'Оценка',
  request: 'Запрос',
}

const exactDetailMessages: Record<string, string> = {
  'A user with the same email already exists.': 'Пользователь с таким email уже зарегистрирован.',
  'Invalid email or password.': 'Неверный email или пароль.',
  'Invalid service client credentials.': 'Неверный идентификатор сервиса или секрет.',
  'No analysis texts are available for voting.': 'Сейчас нет текстов для оценки.',
  'Analysis text voting is unavailable because AnalysisCapture is disabled.': 'Оценка текстов сейчас временно недоступна.',
  'Missing X-CSRF-Token header.': 'Сессия устарела. Обновите страницу и попробуйте ещё раз.',
  'The supplied CSRF token is invalid.': 'Сессия устарела. Обновите страницу и попробуйте ещё раз.',
  'Failed to reach model service.': 'Сервис анализа временно недоступен. Попробуйте позже.',
  'Timed out while calling model service.': 'Сервис анализа отвечает слишком долго. Попробуйте ещё раз.',
  'Model service returned a batch response with an unexpected number of items.': 'Не удалось обработать пакетный анализ. Попробуйте ещё раз.',
  'Model service returned an empty response body.': 'Сервис анализа временно недоступен. Попробуйте позже.',
  'Model service returned an unsupported content type.': 'Сервис анализа временно недоступен. Попробуйте позже.',
  'Model service returned malformed JSON.': 'Сервис анализа временно недоступен. Попробуйте позже.',
  'Model service returned an invalid prediction payload.': 'Сервис анализа временно недоступен. Попробуйте позже.',
}

const exactValidationMessages: Record<string, string> = {
  'Email is required.': 'Укажите email.',
  'Password must contain at least 8 characters.': 'Пароль должен содержать минимум 8 символов.',
  'Email and password are required.': 'Укажите email и пароль.',
  'clientId and clientSecret are required.': 'Заполните обязательные поля запроса.',
  'Text must not be blank.': 'Введите текст для анализа.',
  "Report level must be either 'summary' or 'full'.": 'Выбран недопустимый режим анализа.',
  'Batch must contain at least one item.': 'Добавьте хотя бы один текст.',
  "Vote must be either 'toxic' or 'nonToxic'.": 'Выберите допустимый вариант оценки.',
}

const statusMessages: Partial<Record<number, string>> = {
  400: 'Проверьте заполнение формы и попробуйте ещё раз.',
  401: 'Не удалось выполнить действие. Проверьте данные и попробуйте ещё раз.',
  403: 'У вас нет доступа к этому действию.',
  404: 'Нужные данные не найдены.',
  409: 'Такое действие сейчас выполнить нельзя.',
  500: 'На сервере произошла ошибка. Попробуйте позже.',
  503: 'Сервис временно недоступен. Попробуйте позже.',
  504: 'Сервис отвечает слишком долго. Попробуйте ещё раз.',
}

function translateValidationMessage(message: string) {
  if (exactValidationMessages[message]) {
    return exactValidationMessages[message]
  }

  const batchLimitMatch = /^Batch size must not exceed (\d+)\.$/.exec(message)
  if (batchLimitMatch) {
    return `Можно отправить не больше ${batchLimitMatch[1]} текстов за один раз.`
  }

  return message
}

function translateDetailMessage(detail: string) {
  if (exactDetailMessages[detail]) {
    return exactDetailMessages[detail]
  }

  if (/^Analysis text '.+' was not found\.$/.test(detail)) {
    return 'Текст не найден или уже недоступен.'
  }

  return detail
}

export function resolveProblemErrors(problem: ProblemDetails | null): ResolvedProblemError[] {
  const errors = problem?.errors ?? []

  return errors.map((item) => ({
    field: item.field,
    label: fieldLabels[item.field] ?? item.field,
    message: translateValidationMessage(item.message),
  }))
}

function resolveRouteSpecificMessage(path: string, method: string, status: number) {
  const normalizedMethod = method.toUpperCase()

  if (normalizedMethod === 'POST' && path === '/api/v1/auth/register' && status === 409) {
    return 'Пользователь с таким email уже зарегистрирован.'
  }

  if (normalizedMethod === 'POST' && path === '/api/v1/auth/login' && status === 401) {
    return 'Неверный email или пароль.'
  }

  if (normalizedMethod === 'POST' && path === '/api/v1/auth/logout' && status === 400) {
    return 'Сессия устарела. Обновите страницу и попробуйте ещё раз.'
  }

  return null
}

export function resolveProblemMessage(
  problem: ProblemDetails | null,
  status: number,
  statusText: string,
  path: string,
  method: string,
) {
  const routeSpecificMessage = resolveRouteSpecificMessage(path, method, status)
  if (routeSpecificMessage) {
    return routeSpecificMessage
  }

  if (problem?.code && problemCodeMessages[problem.code]) {
    return problemCodeMessages[problem.code]
  }

  const resolvedErrors = resolveProblemErrors(problem)
  if (resolvedErrors.length > 0) {
    return resolvedErrors.map((item) => item.message).join(' ')
  }

  if (problem?.detail) {
    return translateDetailMessage(problem.detail)
  }

  if (problem?.title === 'CSRF token validation failed.') {
    return 'Сессия устарела. Обновите страницу и попробуйте ещё раз.'
  }

  if (problem?.title && problem.title !== statusText && problem.title !== 'Conflict.' && problem.title !== 'Request validation failed.') {
    return problem.title
  }

  return statusMessages[status] ?? statusText ?? 'Сервер вернул неожиданную ошибку.'
}

export function formatProblemErrorItem(item: ProblemDetailsErrorItem) {
  const label = fieldLabels[item.field] ?? item.field
  const message = translateValidationMessage(item.message)

  return item.field === 'request' ? message : `${label}: ${message}`
}
