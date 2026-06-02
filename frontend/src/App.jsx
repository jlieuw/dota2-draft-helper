import React, { useState, useEffect, useRef } from 'react'
import { useWebSocket } from './useWebSocket'
import { DraftBoard } from './components/DraftBoard'
import { SuggestionList } from './components/SuggestionList'
import { StatusBar } from './components/StatusBar'
import { MyHeroesPanel } from './components/MyHeroesPanel'

const s = {
  app: { display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' },

  // ── Header ──────────────────────────────────────────────────────────────────
  header: {
    display: 'grid',
    gridTemplateColumns: '1fr auto 1fr',
    alignItems: 'center',
    padding: '0 16px',
    height: 44,
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
    gap: 12,
  },
  brand: { display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 14, letterSpacing: '0.04em' },
  logo:  { fontSize: 18 },
  patchBadge: {
    display: 'inline-block', padding: '2px 7px', borderRadius: 4,
    background: 'var(--surface2)', border: '1px solid var(--border)',
    fontSize: 11, color: 'var(--accent)', fontWeight: 600, letterSpacing: '0.04em',
  },

  // ── Nav tabs ────────────────────────────────────────────────────────────────
  nav: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2, height: '100%' },
  navTab: (active) => ({
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '0 14px', height: '100%',
    fontSize: 12, fontWeight: active ? 600 : 400,
    color: active ? 'var(--text)' : 'var(--muted)',
    cursor: 'pointer', border: 'none', background: 'transparent',
    borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
    transition: 'color 0.15s, border-color 0.15s',
    whiteSpace: 'nowrap',
  }),
  navBadge: {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    width: 6, height: 6, borderRadius: '50%', background: 'var(--good)', flexShrink: 0,
  },
  navExternal: {
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '3px 10px', borderRadius: 4,
    border: '1px solid var(--border)',
    background: 'transparent', color: 'var(--muted)',
    fontSize: 11, fontWeight: 400, cursor: 'pointer',
    textDecoration: 'none', whiteSpace: 'nowrap',
    transition: 'color 0.15s, border-color 0.15s',
  },

  // ── Connection indicators ────────────────────────────────────────────────────
  connGroup: { display: 'flex', alignItems: 'center', gap: 14, justifyContent: 'flex-end' },
  connItem:  { display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 },
  dot: (color) => ({ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }),
  connLabel: { color: 'var(--muted)' },
  connValue: (ok) => ({ color: ok ? 'var(--good)' : 'var(--muted)', fontWeight: ok ? 500 : 400 }),

  // ── Page content ─────────────────────────────────────────────────────────────
  loadingBanner: {
    padding: '8px 16px', background: 'rgba(240,165,0,0.1)',
    borderBottom: '1px solid rgba(240,165,0,0.3)', fontSize: 12, color: 'var(--accent)', textAlign: 'center',
  },
  body: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  waitingBanner: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', flex: 1, gap: 10, color: 'var(--muted)', fontSize: 13,
  },
  waitingHint: { fontSize: 11, color: 'var(--border)', maxWidth: 320, textAlign: 'center', lineHeight: 1.6 },
  myHeroesPage: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  myHeroesEmpty: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', flex: 1, gap: 8, color: 'var(--muted)', fontSize: 13,
  },
}

const PAGES = [
  { id: 'draft',     label: '⚔️ Draft',     external: false },
  { id: 'my-heroes', label: '👤 My Heroes',  external: false },
  { id: 'simulator', label: '🎮 Simulator',  external: true,  href: '/simulator' },
]

function ConnDot({ ok }) {
  return <span style={s.dot(ok ? 'var(--good)' : 'var(--bad)')} />
}

export default function App() {
  const { data, connected, setRoleFilter, setBrackets } = useWebSocket()
  const [patch, setPatch]         = useState(null)
  const [page, setPage]           = useState('draft')
  const prevPersonal              = useRef(false)

  const draft           = data?.draft || null
  const suggestions     = data?.suggestions || []
  const draftActive     = draft?.active ?? false
  const gsiConnected    = data?.gsi_connected ?? false
  const hasPersonalData = data?.has_personal_data ?? false
  const personalSummary = data?.personal_summary ?? null
  const comfortGames    = data?.comfort_games ?? 30

  // Fetch patch from status endpoint on connect
  useEffect(() => {
    fetch('/api/status')
      .then(r => r.json())
      .then(d => { if (d.current_patch) setPatch(d.current_patch) })
      .catch(() => {})
  }, [connected])

  // Auto-switch to Draft page when a game draft starts
  useEffect(() => {
    if (draftActive) setPage('draft')
  }, [draftActive])

  // Track when personal data first loads so we can show the badge
  const personalJustLoaded = hasPersonalData && !prevPersonal.current
  useEffect(() => { prevPersonal.current = hasPersonalData }, [hasPersonalData])

  return (
    <div style={s.app}>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <header style={s.header}>

        {/* Left: brand */}
        <div style={s.brand}>
          <span style={s.logo}>⚔️</span>
          Dota Draft Helper
          {patch && <span style={s.patchBadge}>{patch}</span>}
        </div>

        {/* Center: nav tabs */}
        <nav style={s.nav}>
          {PAGES.map(p => {
            if (p.external) {
              return (
                <a key={p.id} href={p.href} target="_blank" rel="noreferrer" style={s.navExternal}>
                  {p.label} ↗
                </a>
              )
            }
            const isMyHeroes = p.id === 'my-heroes'
            const showBadge  = isMyHeroes && personalJustLoaded
            return (
              <button
                key={p.id}
                style={s.navTab(page === p.id)}
                onClick={() => setPage(p.id)}
                title={isMyHeroes && !hasPersonalData ? 'Open Dota 2 to load your hero stats' : undefined}
              >
                {p.label}
                {isMyHeroes && hasPersonalData && (
                  <span
                    style={s.navBadge}
                    title="Personal hero stats loaded"
                  />
                )}
              </button>
            )
          })}
        </nav>

        {/* Right: connection status */}
        <div style={s.connGroup}>
          <div style={s.connItem}>
            <ConnDot ok={connected} />
            <span style={s.connLabel}>App</span>
            <span style={s.connValue(connected)}>{connected ? 'running' : 'offline'}</span>
          </div>
          <div style={s.connItem} title={gsiConnected ? 'Dota 2 is sending events' : 'Waiting — open Dota 2 and wait ~30s'}>
            <ConnDot ok={gsiConnected} />
            <span style={s.connLabel}>Dota 2</span>
            <span style={s.connValue(gsiConnected)}>{gsiConnected ? 'connected' : 'waiting…'}</span>
          </div>
        </div>

      </header>

      {/* ── Loading banner ────────────────────────────────────────────── */}
      {connected && !data && (
        <div style={s.loadingBanner}>
          Loading hero data… (first run may take a few minutes to download matchup data)
        </div>
      )}

      {/* ── Page body ─────────────────────────────────────────────────── */}
      <div style={s.body}>

        {/* Draft page */}
        {page === 'draft' && (
          draftActive ? (
            <>
              <DraftBoard draft={draft} />
              <SuggestionList
                suggestions={suggestions}
                draftActive={draftActive}
                onRoleChange={setRoleFilter}
                onBracketsChange={setBrackets}
                hasPersonalData={hasPersonalData}
                comfortGames={comfortGames}
              />
            </>
          ) : (
            <div style={s.waitingBanner}>
              {!gsiConnected ? (
                <>
                  <span>⏳ Waiting for Dota 2…</span>
                  <span style={s.waitingHint}>
                    Open Dota 2 and wait ~30 seconds. Or test with the{' '}
                    <a href="/simulator" target="_blank" style={{ color: 'var(--accent)' }}>Draft Simulator</a>.
                  </span>
                </>
              ) : (
                <>
                  <span>✅ Dota 2 connected</span>
                  <span style={s.waitingHint}>
                    Queue for Captain's Mode — suggestions appear automatically when the draft starts.
                    <br /><br />
                    <a href="/simulator" target="_blank" style={{ color: 'var(--accent)' }}>Open Draft Simulator</a> to test without a game.
                  </span>
                </>
              )}
            </div>
          )
        )}

        {/* My Heroes page */}
        {page === 'my-heroes' && (
          <div style={s.myHeroesPage}>
            {personalSummary ? (
              <MyHeroesPanel summary={personalSummary} />
            ) : (
              <div style={s.myHeroesEmpty}>
                <span>👤 No hero stats loaded yet</span>
                <span style={s.waitingHint}>
                  Open Dota 2 — your hero stats will load automatically once the app detects your account.
                </span>
              </div>
            )}
          </div>
        )}

      </div>

      <StatusBar />
    </div>
  )
}

