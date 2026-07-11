import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, clearSession, getStoredUser, saveSession } from './api'
import { applyTheme, getTheme } from './theme'

const POLL_MS = 15000
const ACTIVE = new Set(['requested', 'received', 'in_progress'])

const STATUS_LABELS = {
  requested: 'Requested',
  received: 'Received',
  in_progress: 'In progress',
  completed: 'Completed',
  picked_up: 'Picked up',
  cancelled: 'Cancelled',
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Self-contained dark-mode toggle: owns its state and writes through to the
// document + localStorage, so it can be dropped anywhere without prop drilling.
function ThemeToggle() {
  const [theme, setTheme] = useState(getTheme)

  useEffect(() => { applyTheme(theme) }, [theme])

  const dark = theme === 'dark'
  return (
    <button
      type="button"
      className="btn ghost icon-btn"
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={dark}
      title={dark ? 'Light mode' : 'Dark mode'}
    >
      {dark ? '☀️' : '🌙'}
    </button>
  )
}

// ---- small utilities -------------------------------------------------------
function pad(n) {
  return String(n).padStart(2, '0')
}

// Build valid on-grid, in-hours slot times for a chosen date (matches backend).
function slotOptions(info, dateStr) {
  if (!info || !dateStr) return []
  const [oh, om] = info.open_time.split(':').map(Number)
  const [ch, cm] = info.close_time.split(':').map(Number)
  const step = info.slot_minutes
  const out = []
  for (let m = oh * 60 + om; m <= ch * 60 + cm; m += step) {
    const hh = Math.floor(m / 60)
    const mm = m % 60
    out.push(`${pad(hh)}:${pad(mm)}`)
  }
  return out
}

function formatDropoff(value) {
  if (!value) return 'Flexible'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// dropoff asc, flexible (null) last, then created_at asc.
function queueSort(a, b) {
  const av = a.dropoff_at
  const bv = b.dropoff_at
  if (av && bv) {
    if (av !== bv) return av < bv ? -1 : 1
    return a.created_at < b.created_at ? -1 : 1
  }
  if (av && !bv) return -1
  if (!av && bv) return 1
  return a.created_at < b.created_at ? -1 : 1
}

// ============================================================================
export default function App() {
  const [user, setUser] = useState(getStoredUser())
  const [info, setInfo] = useState(null)
  const [showAuth, setShowAuth] = useState(false)
  const [authMode, setAuthMode] = useState('login')

  useEffect(() => {
    api.info().then(setInfo).catch(() => setInfo(null))
  }, [])

  function handleLogout() {
    clearSession()
    setUser(null)
    setShowAuth(false)
  }

  function goAuth(mode) {
    setAuthMode(mode)
    setShowAuth(true)
  }

  if (!user) {
    return showAuth ? (
      <AuthScreen
        info={info}
        initialMode={authMode}
        onAuthed={setUser}
        onBack={() => setShowAuth(false)}
      />
    ) : (
      <Landing info={info} onStart={goAuth} />
    )
  }

  return user.role === 'stringer' ? (
    <StringerView user={user} info={info} onLogout={handleLogout} />
  ) : (
    <CustomerView user={user} info={info} onLogout={handleLogout} />
  )
}

// ---- Landing / hero --------------------------------------------------------
function Landing({ info, onStart }) {
  const hours = info ? `${info.open_time}–${info.close_time}` : null
  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="landing-brand">🎾 Strings by Evan</div>
        <div className="landing-nav-actions">
          <ThemeToggle />
          <button className="btn ghost" onClick={() => onStart('login')}>Log in</button>
        </div>
      </nav>

      <header className="hero">
        <div className="hero-copy">
          <span className="hero-eyebrow">Local racquet stringing</span>
          <h1 className="hero-title">Fresh strings,<br />ready to play.</h1>
          <p className="hero-sub">
            Pro stringing dialed to your exact tension. Drop off your racquet, pick your
            setup, and get back on court fast.
          </p>
          <div className="hero-cta">
            <button className="btn primary big" onClick={() => onStart('signup')}>
              Request a stringing
            </button>
            <button className="btn ghost big" onClick={() => onStart('login')}>
              I have an account
            </button>
          </div>
          {info && (
            <p className="hero-hours">Open {hours} · {info.turnaround_note}</p>
          )}
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="court">
            <div className="court-glow" />
            <div className="court-net" />
            <div className="ball-shadow" />
            <div className="ball" />
          </div>
        </div>
      </header>

      <section className="features">
        <div className="feature card">
          <div className="feature-icon">🎯</div>
          <h3>Your exact tension</h3>
          <p>Choose any tension from 40–60 lbs. We string it to spec, every time.</p>
        </div>
        <div className="feature card">
          <div className="feature-icon">🕒</div>
          <h3>Drop off on your schedule</h3>
          <p>Pick a drop-off time{hours ? ` within ${hours}` : ''}, or keep it flexible — no appointment needed.</p>
        </div>
        <div className="feature card">
          <div className="feature-icon">⚡</div>
          <h3>Fast turnaround</h3>
          <p>{info ? info.turnaround_note : 'Most racquets are ready within a day.'}</p>
        </div>
      </section>

      <footer className="landing-foot">
        <span className="landing-brand">🎾 Strings by Evan</span>
        <button className="btn primary" onClick={() => onStart('signup')}>Get started</button>
      </footer>
    </div>
  )
}

// ---- Auth ------------------------------------------------------------------
function AuthScreen({ info, onAuthed, onBack, initialMode = 'login' }) {
  const [mode, setMode] = useState(initialMode)
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'customer', stringer_code: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const fn = mode === 'login' ? api.login : api.register
      const payload =
        mode === 'login'
          ? { email: form.email, password: form.password }
          : form
      const res = await fn(payload)
      saveSession(res)
      onAuthed(res.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div className="auth-top">
          {onBack ? (
            <button type="button" className="back-link" onClick={onBack}>← Back</button>
          ) : <span />}
          <ThemeToggle />
        </div>
        <div className="brand">🎾 Strings by Evan</div>
        <div className="tabs">
          <button className={mode === 'login' ? 'tab active' : 'tab'} onClick={() => setMode('login')}>
            Log in
          </button>
          <button className={mode === 'register' ? 'tab active' : 'tab'} onClick={() => setMode('register')}>
            Sign up
          </button>
        </div>
        <form onSubmit={submit} className="stack">
          {mode === 'register' && (
            <label className="field">
              <span>Name</span>
              <input value={form.name} onChange={set('name')} required />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input type="email" value={form.email} onChange={set('email')} required />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" value={form.password} onChange={set('password')} required minLength={6} />
          </label>
          {mode === 'register' && (
            <label className="field">
              <span>I am a</span>
              <select value={form.role} onChange={set('role')}>
                <option value="customer">Customer</option>
                <option value="stringer">Stringer</option>
              </select>
            </label>
          )}
          {mode === 'register' && form.role === 'stringer' && (
            <label className="field">
              <span>Stringer access code</span>
              <input
                type="password"
                value={form.stringer_code}
                onChange={set('stringer_code')}
                placeholder="Owner-only code"
                autoComplete="off"
              />
            </label>
          )}
          {error && <div className="alert error">{error}</div>}
          <button className="btn primary" disabled={busy} type="submit">
            {busy ? '…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>
        {info && <p className="muted center">Open {info.open_time}–{info.close_time}</p>}
      </div>
    </div>
  )
}

// ---- Shared top bar --------------------------------------------------------
function TopBar({ title, user, onLogout, right }) {
  return (
    <header className="topbar">
      <div className="topbar-title">{title}</div>
      <div className="topbar-actions">
        {right}
        <ThemeToggle />
        <span className="who">{user.name}</span>
        <button className="btn ghost logout" onClick={onLogout}>Log out</button>
      </div>
    </header>
  )
}

// ---- Customer --------------------------------------------------------------
function CustomerView({ user, info, onLogout }) {
  const [jobs, setJobs] = useState([])
  const [confirmation, setConfirmation] = useState(null)

  const load = useCallback(() => {
    api.listJobs().then(setJobs).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])

  function onCreated(job) {
    setConfirmation(job)
    load()
  }

  return (
    <div className="app">
      <TopBar title="🎾 My Racquets" user={user} onLogout={onLogout} />

      {/* Drop-off banner — carries the turnaround expectation (Task 3). */}
      {info && (
        <div className="banner">
          <strong>Drop-off:</strong> open {info.open_time}–{info.close_time},{' '}
          {info.slot_minutes}-minute slots. <span className="turnaround">{info.turnaround_note}</span>
        </div>
      )}

      <main className="content">
        {confirmation ? (
          <Confirmation job={confirmation} info={info} onDone={() => setConfirmation(null)} />
        ) : (
          <NewJobForm info={info} onCreated={onCreated} />
        )}

        <section className="card">
          <h2>Your requests</h2>
          {jobs.length === 0 && <p className="muted">No requests yet.</p>}
          <ul className="joblist">
            {jobs.map((j) => (
              <li key={j.id} className="jobrow">
                <div>
                  <div className="jobrow-main">{j.racquet}</div>
                  <div className="muted small">
                    {formatDropoff(j.dropoff_at)}
                    {j.tension ? ` · ${j.tension} lbs` : ''}
                  </div>
                </div>
                <StatusPill status={j.status} />
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}

const OTHER = '__other__'

function NewJobForm({ info, onCreated }) {
  const [racquets, setRacquets] = useState([])
  const [racquetChoice, setRacquetChoice] = useState('')
  const [customRacquet, setCustomRacquet] = useState('')
  const [stringPref, setStringPref] = useState('')
  const [tension, setTension] = useState('')
  const [notes, setNotes] = useState('')
  const [flexible, setFlexible] = useState(true)
  const [date, setDate] = useState('')
  const [slot, setSlot] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.racquets().then(setRacquets).catch(() => setRacquets([]))
  }, [])

  const slots = useMemo(() => slotOptions(info, date), [info, date])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)

    const racquet = racquetChoice === OTHER ? customRacquet.trim() : racquetChoice
    if (!racquet) {
      setError('Pick your racquet, or choose "Other" and type it in.')
      setBusy(false)
      return
    }
    if (tension === '') {
      setError('Enter a string tension between 40 and 60 lbs.')
      setBusy(false)
      return
    }

    let dropoff_at = null
    if (!flexible) {
      if (!date || !slot) {
        setError('Pick a date and time, or choose Flexible.')
        setBusy(false)
        return
      }
      dropoff_at = `${date}T${slot}:00`
    }
    try {
      const job = await api.createJob({
        racquet,
        string_preference: stringPref || null,
        tension: Number(tension),
        notes: notes || null,
        dropoff_at,
      })
      setRacquetChoice(''); setCustomRacquet(''); setStringPref(''); setTension('')
      setNotes(''); setFlexible(true); setDate(''); setSlot('')
      onCreated(job)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h2>Request a stringing</h2>
      <form onSubmit={submit} className="stack">
        <label className="field">
          <span>Racquet</span>
          <select value={racquetChoice} onChange={(e) => setRacquetChoice(e.target.value)} required>
            <option value="">Select your racquet…</option>
            {racquets.map((r) => <option key={r} value={r}>{r}</option>)}
            <option value={OTHER}>Other (not listed)</option>
          </select>
        </label>
        {racquetChoice === OTHER && (
          <label className="field">
            <span>Racquet model</span>
            <input
              value={customRacquet}
              onChange={(e) => setCustomRacquet(e.target.value)}
              required
              placeholder="Brand and model"
            />
          </label>
        )}
        <label className="field">
          <span>String preference (optional)</span>
          <input value={stringPref} onChange={(e) => setStringPref(e.target.value)} placeholder="Luxilon ALU Power 16L" />
        </label>
        <label className="field">
          <span>Tension in lbs (40–60)</span>
          <input
            type="number"
            min={40}
            max={60}
            step={1}
            value={tension}
            onChange={(e) => setTension(e.target.value)}
            required
            placeholder="e.g. 55"
          />
        </label>
        <label className="field">
          <span>Notes (optional)</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
        </label>

        <label className="checkbox">
          <input type="checkbox" checked={flexible} onChange={(e) => setFlexible(e.target.checked)} />
          <span>Flexible drop-off (I'll come by whenever)</span>
        </label>

        {!flexible && (
          <div className="row">
            <label className="field">
              <span>Date</span>
              <input type="date" value={date} onChange={(e) => { setDate(e.target.value); setSlot('') }} />
            </label>
            <label className="field">
              <span>Time</span>
              <select value={slot} onChange={(e) => setSlot(e.target.value)}>
                <option value="">Select…</option>
                {slots.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
        )}

        {error && <div className="alert error">{error}</div>}
        <button className="btn primary" disabled={busy} type="submit">
          {busy ? 'Submitting…' : 'Submit request'}
        </button>
      </form>
    </section>
  )
}

function Confirmation({ job, info, onDone }) {
  return (
    <section className="card confirmation">
      <div className="check">✓</div>
      <h2>Request received</h2>
      <p>
        <strong>{job.racquet}</strong>
        {job.string_preference ? ` · ${job.string_preference}` : ''}
        {job.tension ? ` · ${job.tension} lbs` : ''}
      </p>
      <p className="muted">Drop-off: {formatDropoff(job.dropoff_at)}</p>
      {/* Address only appears once a specific drop-off time was set. */}
      {job.dropoff_at && job.dropoff_address && (
        <div className="dropoff-address">
          <span className="dropoff-address-label">Drop off your racquet at</span>
          <span className="dropoff-address-value">📍 {job.dropoff_address}</span>
        </div>
      )}
      {info && <p className="turnaround banner-inline">{info.turnaround_note}</p>}
      <button className="btn primary" onClick={onDone}>Request another</button>
    </section>
  )
}

// ---- Stringer --------------------------------------------------------------
function StringerView({ user, info, onLogout }) {
  const [jobs, setJobs] = useState([])
  const [queueOpen, setQueueOpen] = useState(false)
  const [editing, setEditing] = useState(null) // job in the reschedule modal
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      setJobs(await api.listJobs())
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  // Initial load + light polling. Pause while the edit modal is open so a
  // refetch doesn't disrupt editing.
  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (editing) return undefined
    const id = setInterval(load, POLL_MS)
    return () => clearInterval(id)
  }, [load, editing])

  const active = useMemo(
    () => jobs.filter((j) => ACTIVE.has(j.status)).sort(queueSort),
    [jobs],
  )

  const stats = useMemo(() => {
    const by = {}
    for (const j of jobs) by[j.status] = (by[j.status] || 0) + 1
    return by
  }, [jobs])

  async function completeJob(id) {
    await api.updateJob(id, { status: 'completed' })
    await load() // always refresh right after an action
  }

  async function saveEdit(id, patch) {
    await api.updateJob(id, patch)
    setEditing(null)
    await load()
  }

  return (
    <div className="app">
      <TopBar
        title="🎾 Stringer Console"
        user={user}
        onLogout={onLogout}
        right={
          <button
            className="btn queue-btn"
            onClick={() => setQueueOpen((v) => !v)}
            aria-expanded={queueOpen}
            aria-controls="queue-panel"
          >
            Queue <span className="queue-count">{active.length}</span>
          </button>
        }
      />

      <main className="content">
        {error && <div className="alert error">{error}</div>}
        <StatsRow stats={stats} total={jobs.length} />

        <section className="card">
          <h2>All jobs</h2>
          {jobs.length === 0 && <p className="muted">No jobs yet.</p>}
          <table className="jobs-table">
            <thead>
              <tr><th>Customer</th><th>Racquet</th><th>Drop-off</th><th>Tension</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.customer?.name}</td>
                  <td>{j.racquet}</td>
                  <td>{formatDropoff(j.dropoff_at)}</td>
                  <td>{j.tension ? `${j.tension} lbs` : '—'}</td>
                  <td><StatusPill status={j.status} /></td>
                  <td><button className="btn ghost small" onClick={() => setEditing(j)}>Manage</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>

      <QueueDrawer
        open={queueOpen}
        active={active}
        onClose={() => setQueueOpen(false)}
        onComplete={completeJob}
      />

      {editing && (
        <EditModal
          job={editing}
          info={info}
          onCancel={() => setEditing(null)}
          onSave={saveEdit}
        />
      )}
    </div>
  )
}

function StatsRow({ stats, total }) {
  const cards = [
    { label: 'Active', value: (stats.requested || 0) + (stats.received || 0) + (stats.in_progress || 0) },
    { label: 'In progress', value: stats.in_progress || 0 },
    { label: 'Completed', value: stats.completed || 0 },
    { label: 'Total', value: total },
  ]
  return (
    <div className="stats">
      {cards.map((c) => (
        <div className="stat card" key={c.label}>
          <div className="stat-value">{c.value}</div>
          <div className="stat-label">{c.label}</div>
        </div>
      ))}
    </div>
  )
}

function QueueDrawer({ open, active, onClose, onComplete }) {
  // Track rows mid-strike so the animation plays before removal.
  const [striking, setStriking] = useState(() => new Set())
  const timers = useRef([])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  function crossOff(id) {
    const delay = prefersReducedMotion() ? 0 : 450
    setStriking((prev) => new Set(prev).add(id))
    const t = setTimeout(async () => {
      try {
        await onComplete(id) // completes + refetch; row leaves active set
      } finally {
        setStriking((prev) => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
      }
    }, delay)
    timers.current.push(t)
  }

  return (
    <>
      {open && <div className="scrim" onClick={onClose} />}
      <aside
        id="queue-panel"
        className={open ? 'queue-panel open' : 'queue-panel'}
        aria-hidden={!open}
      >
        <div className="queue-head">
          <h3>Active queue <span className="queue-count">{active.length}</span></h3>
          <button className="btn ghost small" onClick={onClose} aria-label="Close queue">✕</button>
        </div>
        {active.length === 0 && <p className="muted queue-empty">Nothing in the queue. 🎉</p>}
        <ul className="queue-list">
          {active.map((j) => (
            <li key={j.id} className={striking.has(j.id) ? 'queue-item striking' : 'queue-item'}>
              <div className="queue-item-body">
                <div className="queue-item-top">
                  <span className="queue-name">{j.customer?.name}</span>
                  <StatusPill status={j.status} />
                </div>
                <div className="queue-racquet">{j.racquet}</div>
                <div className="muted small">
                  {formatDropoff(j.dropoff_at)}
                  {j.tension ? ` · ${j.tension} lbs` : ''}
                </div>
              </div>
              <button
                className="btn crossoff"
                onClick={() => crossOff(j.id)}
                disabled={striking.has(j.id)}
                title="Mark completed"
                aria-label={`Mark ${j.racquet} completed`}
              >
                ✓
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </>
  )
}

function EditModal({ job, info, onCancel, onSave }) {
  const [status, setStatus] = useState(job.status)
  const [tension, setTension] = useState(job.tension ?? '')
  const [flexible, setFlexible] = useState(!job.dropoff_at)
  const [date, setDate] = useState(job.dropoff_at ? job.dropoff_at.slice(0, 10) : '')
  const [slot, setSlot] = useState(job.dropoff_at ? job.dropoff_at.slice(11, 16) : '')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const slots = useMemo(() => slotOptions(info, date), [info, date])

  async function save() {
    setBusy(true)
    setError(null)
    const patch = { status, tension: tension === '' ? null : Number(tension) }
    if (flexible) {
      patch.dropoff_at = null
    } else if (date && slot) {
      patch.dropoff_at = `${date}T${slot}:00`
    }
    try {
      await onSave(job.id, patch)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-scrim" onClick={onCancel}>
      <div className="card modal" onClick={(e) => e.stopPropagation()}>
        <h3>Manage · {job.racquet}</h3>
        <p className="muted small">{job.customer?.name}</p>

        <label className="field">
          <span>Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.keys(STATUS_LABELS).map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Tension in lbs (40–60)</span>
          <input
            type="number"
            min={40}
            max={60}
            step={1}
            value={tension}
            onChange={(e) => setTension(e.target.value)}
            placeholder="e.g. 55"
          />
        </label>

        <label className="checkbox">
          <input type="checkbox" checked={flexible} onChange={(e) => setFlexible(e.target.checked)} />
          <span>Flexible drop-off</span>
        </label>

        {!flexible && (
          <div className="row">
            <label className="field">
              <span>Date</span>
              <input type="date" value={date} onChange={(e) => { setDate(e.target.value); setSlot('') }} />
            </label>
            <label className="field">
              <span>Time</span>
              <select value={slot} onChange={(e) => setSlot(e.target.value)}>
                <option value="">Select…</option>
                {slots.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
        )}

        {error && <div className="alert error">{error}</div>}
        <div className="modal-actions">
          <button className="btn ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  return <span className={`pill pill-${status}`}>{STATUS_LABELS[status] || status}</span>
}
