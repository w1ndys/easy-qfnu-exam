export function jsonError(message: string, status: number) {
  return Response.json({ ok: false, error: message }, { status })
}
