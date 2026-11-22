export function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
export function apiError(error) {
  return error?.userMessage || error?.message || '처리 중 오류가 발생했습니다.'
}