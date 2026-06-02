import React from 'react'
import { HeroPortrait } from './HeroPortrait'

const s = {
  board: {
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
    padding: '12px 16px', background: 'var(--surface)', borderBottom: '1px solid var(--border)',
  },
  team: { display: 'flex', flexDirection: 'column', gap: 8 },
  teamHeader: { fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' },
  radiantHeader: { color: 'var(--radiant)' },
  direHeader:    { color: 'var(--dire)' },
  myTeamBadge: {
    display: 'inline-block', fontSize: 9, padding: '1px 5px', borderRadius: 3,
    background: 'var(--accent)', color: '#000', marginLeft: 6, fontWeight: 700, verticalAlign: 'middle',
  },
  picksRow: { display: 'flex', gap: 6, alignItems: 'flex-start' },
  bansRow:  { display: 'flex', gap: 4, alignItems: 'flex-start', flexWrap: 'wrap' },
  banLabel: { fontSize: 9, color: 'var(--muted)', marginBottom: 2 },
  banPortrait: { opacity: 0.55, filter: 'grayscale(40%)' },
  activeBadge: { fontSize: 9, color: 'var(--accent)', fontStyle: 'italic' },
  timer: { fontSize: 12, color: 'var(--accent)', fontWeight: 600, marginLeft: 8 },
}

function TeamSlots({ team, side, myTeam, activeSide, timeRemaining }) {
  const isActive = activeSide === side
  const isMyTeam = myTeam === side
  const picks = team.picks || []
  const bans  = team.bans  || []

  const pickSlots = [...picks, ...Array(5 - picks.length).fill(null)]
  const maxBans   = Math.max(5, bans.length)
  const banSlots  = [...bans, ...Array(maxBans - bans.length).fill(null)]

  const headerStyle = {
    ...s.teamHeader,
    ...(side === 'radiant' ? s.radiantHeader : s.direHeader),
  }

  return (
    <div style={s.team}>
      <div>
        <span style={headerStyle}>{side}</span>
        {isMyTeam && <span style={s.myTeamBadge}>YOU</span>}
        {isActive && <span style={s.activeBadge}> picking{timeRemaining != null ? '' : '…'}</span>}
        {isActive && timeRemaining != null && (
          <span style={s.timer}>{Math.ceil(timeRemaining)}s</span>
        )}
      </div>
      <div style={s.picksRow}>
        {pickSlots.map((hero, i) => <HeroPortrait key={i} hero={hero} />)}
      </div>
      <div>
        <div style={s.banLabel}>Bans</div>
        <div style={s.bansRow}>
          {banSlots.map((hero, i) => (
            <div key={i} style={hero ? s.banPortrait : undefined}>
              <HeroPortrait hero={hero} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function DraftBoard({ draft }) {
  if (!draft) return null
  return (
    <div style={s.board}>
      <TeamSlots
        team={draft.radiant}
        side="radiant"
        myTeam={draft.my_team}
        activeSide={draft.active_team}
        timeRemaining={draft.active_team === 'radiant' ? draft.time_remaining : null}
      />
      <TeamSlots
        team={draft.dire}
        side="dire"
        myTeam={draft.my_team}
        activeSide={draft.active_team}
        timeRemaining={draft.active_team === 'dire' ? draft.time_remaining : null}
      />
    </div>
  )
}
