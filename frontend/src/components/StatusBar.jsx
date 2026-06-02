import React, { useState, useEffect } from 'react'

const s = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    padding: '5px 16px',
    background: 'var(--surface)',
    borderTop: '1px solid var(--border)',
    fontSize: 11,
    color: 'var(--muted)',
    flexShrink: 0,
    flexWrap: 'wrap',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
  },
  label: {
    color: 'var(--muted)',
  },
  value: {
    color: 'var(--text)',
    fontWeight: 500,
  },
  stale: {
    color: 'var(--bad)',
    fontWeight: 600,
  },
  fresh: {
    color: 'var(--good)',
  },
  warn: {
    color: 'var(--accent)',
  },
  dot: (color) => ({
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: color,
    display: 'inline-block',
  }),
  divider: {
    color: 'var(--border)',
    userSelect: 'none',
  },
  stratzBadge: {
    padding: '1px 5px',
    borderRadius: 3,
    fontSize: 10,
    fontWeight: 600,
  },
  patchBadge: (stale) => ({
    padding: '1px 5px',
    borderRadius: 3,
    fontSize: 10,
    fontWeight: 600,
    background: stale ? 'rgba(248,81,73,0.15)' : 'rgba(63,185,80,0.15)',
    color: stale ? 'var(--bad)' : 'var(--good)',
  }),
}

function AgeLabel({ ageInfo, staleAfterHours = 26 }) {
  if (!ageInfo) return <span style={s.stale}>no data</span>
  const { hours_ago } = ageInfo
  const isStale = hours_ago > staleAfterHours
  if (hours_ago < 1) return <span style={s.fresh}>just now</span>
  if (hours_ago < 24) return <span style={isStale ? s.stale : s.fresh}>{hours_ago}h ago</span>
  return <span style={s.stale}>{Math.floor(hours_ago / 24)}d ago ⚠</span>
}

function PatchBadge({ dataPatch, currentPatch }) {
  if (!dataPatch) return null
  const stale = currentPatch && dataPatch !== currentPatch
  return (
    <span
      style={s.patchBadge(stale)}
      title={stale ? `Data from patch ${dataPatch} — current patch is ${currentPatch}. Restart to re-fetch.` : `Data is current (patch ${dataPatch})`}
    >
      {stale ? `⚠ ${dataPatch}` : dataPatch}
    </span>
  )
}

export function StatusBar() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    const fetch_ = () =>
      fetch('/api/status')
        .then(r => r.json())
        .then(setStatus)
        .catch(() => {})

    fetch_()
    const interval = setInterval(fetch_, 30_000)
    return () => clearInterval(interval)
  }, [])

  if (!status) return null

  const currentPatch = status.current_patch
  const anyPatchWarn = status.patch_warnings && Object.values(status.patch_warnings).some(Boolean)

  return (
    <div style={s.bar}>
      {/* Current game patch */}
      <div style={s.item}>
        <span style={s.label}>Patch</span>
        <span style={s.value}>{currentPatch || '—'}</span>
      </div>

      <span style={s.divider}>·</span>

      {/* Matchup / counter data */}
      <div style={s.item}>
        <span style={s.label}>Counter data</span>
        <AgeLabel ageInfo={status.matchups} staleAfterHours={26} />
        <PatchBadge dataPatch={status.synergies_patch || status.matchups_patch} currentPatch={currentPatch} />
      </div>

      <span style={s.divider}>·</span>

      {/* Synergy data */}
      <div style={s.item}>
        <span style={s.label}>Synergy data</span>
        {status.has_stratz_token ? (
          <>
            <AgeLabel ageInfo={status.synergies} staleAfterHours={26} />
            <span style={{ ...s.stratzBadge, background: 'rgba(94,161,255,0.15)', color: '#6ea8fe' }}>
              Stratz
            </span>
          </>
        ) : (
          <span style={s.warn} title="Add a free Stratz token in config.json for real synergy data">
            heuristic
          </span>
        )}
      </div>

      {/* Patch-stale warning */}
      {anyPatchWarn && (
        <>
          <span style={s.divider}>·</span>
          <span style={s.stale} title="Some data was fetched on an older patch. Restart the app to re-fetch.">
            ⚠ Old patch data — restart to update
          </span>
        </>
      )}

      {/* Time-stale warning (no patch change, just overdue) */}
      {!anyPatchWarn && status.matchups_need_refresh && (
        <>
          <span style={s.divider}>·</span>
          <span style={s.stale}>⚠ Data stale — restart app to refresh</span>
        </>
      )}
    </div>
  )
}
