// Thin fetch wrapper. Token is kept in localStorage and attached to requests.

// All API calls are served under /api on the same origin (Vercel routes /api/*
// to the FastAPI function; the Vite dev server proxies /api to :8000). Override
// with VITE_API_BASE only if the backend lives on a different origin.
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const TOKEN_KEY = 'tss_token'
const USER_KEY = 'tss_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export function saveSession({ access_token, user }) {
  localStorage.setItem(TOKEN_KEY, access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`

  const resp = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  const data = resp.status === 204 ? null : await resp.json().catch(() => null)
  if (!resp.ok) {
    const detail = data && data.detail ? data.detail : `Request failed (${resp.status})`
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data
}

export const api = {
  info: () => request('/info', { auth: false }),
  racquets: () => request('/racquets', { auth: false }),
  queue: () => request('/queue', { auth: false }),
  register: (payload) => request('/auth/register', { method: 'POST', body: payload, auth: false }),
  verifyEmail: (payload) => request('/auth/verify', { method: 'POST', body: payload, auth: false }),
  resendCode: (payload) => request('/auth/resend', { method: 'POST', body: payload, auth: false }),
  login: (payload) => request('/auth/login', { method: 'POST', body: payload, auth: false }),
  listJobs: () => request('/jobs'),
  createJob: (payload) => request('/jobs', { method: 'POST', body: payload }),
  updateJob: (id, payload) => request(`/jobs/${id}`, { method: 'PATCH', body: payload }),
}
