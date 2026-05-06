export interface ProblemDetailsErrorItem {
  field: string
  message: string
}

export interface ProblemDetails {
  type?: string
  title?: string
  status?: number
  detail?: string
  instance?: string
  code?: string
  errors?: ProblemDetailsErrorItem[]
}
