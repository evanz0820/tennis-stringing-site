// Theme persistence. The initial attribute is set by an inline script in
// index.html (before paint); these helpers keep it in sync afterward.

const KEY = 'tss_theme'

export function getTheme() {
  const saved = localStorage.getItem(KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(KEY, theme)
}
