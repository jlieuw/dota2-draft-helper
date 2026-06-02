import React, { useState, useMemo } from 'react'

const ROLES = ['All', 'Carry', 'Support', 'Nuker', 'Disabler', 'Durable', 'Escape', 'Pusher', 'Initiator']

const BRACKETS = [
  { num: 1, label: 'Herald'   },
  { num: 2, label: 'Guardian' },
  { num: 3, label: 'Crusader' },
  { num: 4, label: 'Archon'   },
  { num: 5, label: 'Legend'   },
  { num: 6, label: 'Ancient'  },
  { num: 7, label: 'Divine'   },
  { num: 8, label: 'Immortal' },
]

const ATTR_COLORS = {
  str: '#e8512b', agi: '#5cb85c', int: '#6ea8fe', all: '#c47eff', uni: '#c47eff',
}

// Column definitions with tooltips explaining what each value means
const COLUMNS = [
  {
    key: 'display_name', label: 'Hero', right: false, isTotal: false,
    tip: 'Hero name. Click to sort alphabetically.',
  },
  {
    key: 'winrate', label: 'Winrate', right: true, isTotal: false,
    tip: 'Global win rate for this hero in the selected rank brackets.\nThis is a patch-level baseline — it does NOT change based on your draft.\nSource: OpenDota public match data.',
  },
  {
    key: 'synergy_score', label: 'Synergy', right: true, isTotal: false,
    tip: 'How much better this hero performs when your current allies are teammates.\nPositive = benefits from your picks. Updates as you pick allies.\nTypical range: -5% to +5%. Dota is balanced — large swings are rare.\nSource: Stratz with-teammate data (requires token) or heuristic fallback.',
  },
  {
    key: 'counter_score', label: 'Counter', right: true, isTotal: false,
    tip: 'How much better this hero performs against the enemy picks.\nPositive = counters the enemy lineup. Updates as enemies pick.\nTypical range: -7% to +7%. Zeros mean no enemies picked yet, or matchup data still loading.\nSource: OpenDota hero matchup data.',
  },
  {
    key: 'personal_winrate', label: 'You', right: true, isTotal: false, personalOnly: true,
    tip: 'Your personal win rate on this hero (OpenDota profile).\nGreen ≥ 55%, grey 45-55%, red < 45%.\nGame count shown in parentheses. Weighted by confidence (full weight at 50+ games).',
  },
  {
    key: 'total_score', label: 'Score', right: true, isTotal: true,
    tip: 'Weighted composite score (0–100).\nWeights: Winrate 25% · Synergy 35% · Counter 40% (+ personal 15% when loaded).\nAdjust weights in config.json.',
  },
]

const s = {
  container: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  toolbar: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '8px 16px', borderBottom: '1px solid var(--border)',
    background: 'var(--surface)', flexWrap: 'wrap', rowGap: 6,
  },
  toolbarLabel: { fontSize: 10, color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', whiteSpace: 'nowrap' },
  roleBtn: (active) => ({
    padding: '2px 8px', borderRadius: 4,
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    background: active ? 'var(--accent)' : 'transparent',
    color: active ? '#000' : 'var(--muted)',
    fontSize: 11, fontWeight: active ? 600 : 400, cursor: 'pointer', transition: 'all 0.1s',
  }),
  divider: { width: 1, height: 18, background: 'var(--border)', flexShrink: 0 },
  bracketBtn: (active) => ({
    padding: '2px 7px', borderRadius: 3,
    border: `1px solid ${active ? '#6ea8fe' : 'var(--border)'}`,
    background: active ? 'rgba(110,168,254,0.12)' : 'transparent',
    color: active ? '#6ea8fe' : 'var(--muted)',
    fontSize: 10, fontWeight: active ? 600 : 400, cursor: 'pointer', transition: 'all 0.1s',
  }),
  clearBrackets: {
    padding: '2px 6px', borderRadius: 3, border: '1px solid var(--border)',
    background: 'transparent', color: 'var(--muted)', fontSize: 10, cursor: 'pointer',
  },
  searchWrap: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 },
  searchInput: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    borderRadius: 4, color: 'var(--text)', padding: '3px 10px',
    fontSize: 12, fontFamily: 'inherit', width: 140,
  },
  tableWrap: { overflow: 'auto', flex: 1 },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: (active) => ({
    padding: '7px 10px', textAlign: 'left', fontSize: 10, fontWeight: 600,
    color: active ? 'var(--accent)' : 'var(--muted)',
    letterSpacing: '0.06em', textTransform: 'uppercase',
    borderBottom: '1px solid var(--border)', position: 'sticky', top: 0,
    background: 'var(--surface)', userSelect: 'none',
    cursor: 'pointer', whiteSpace: 'nowrap',
  }),
  thRight: { textAlign: 'right' },
  row: (i) => ({ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.018)', borderBottom: '1px solid rgba(48,54,61,0.4)' }),
  td: { padding: '5px 10px', verticalAlign: 'middle' },
  tdRight: { textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
  rank: { color: 'var(--muted)', fontSize: 11, width: 26 },
  heroCell: { display: 'flex', alignItems: 'center', gap: 8 },
  heroImg: { width: 38, height: 22, objectFit: 'cover', borderRadius: 2, background: 'var(--surface2)', flexShrink: 0 },
  heroInfo: { display: 'flex', flexDirection: 'column', gap: 1 },
  heroName: { fontWeight: 500, fontSize: 12 },
  heroRoles: { fontSize: 9, color: 'var(--muted)' },
  attrDot: (attr) => ({
    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
    background: ATTR_COLORS[attr] || '#8b949e', marginRight: 4, verticalAlign: 'middle',
  }),
  noData:  { padding: '48px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 },
  waiting: { padding: '48px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 },
}

function bar(value, isCounter) {
  // Small horizontal bar to visualise the delta visually
  if (value == null) return null
  const pct   = Math.min(Math.abs(value) / 7 * 100, 100)  // 7% = full bar
  const color = value > 0 ? 'var(--good)' : value < 0 ? 'var(--bad)' : 'var(--border)'
  return (
    <div style={{ display: 'inline-block', width: 28, height: 4, background: 'var(--surface2)', borderRadius: 2, verticalAlign: 'middle', marginLeft: 5, overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s' }} />
    </div>
  )
}

function SortArrow({ dir }) {
  return <span style={{ marginLeft: 3, fontSize: 8, opacity: 0.7 }}>{dir === 'asc' ? '▲' : '▼'}</span>
}

function ScoreCell({ value, isTotal, showBar }) {
  if (value == null) return <td style={{ ...s.td, ...s.tdRight }}><span style={{ color: 'var(--border)', fontSize: 10 }}>—</span></td>
  const prefix = isTotal ? '' : (value > 0 ? '+' : '')
  const color  = isTotal
    ? 'var(--accent)'
    : value > 2 ? 'var(--good)' : value < -2 ? 'var(--bad)' : 'var(--muted)'
  return (
    <td style={{ ...s.td, ...s.tdRight }}>
      <span style={{ color, fontWeight: isTotal ? 700 : 400, fontSize: isTotal ? 13 : 12 }}>
        {prefix}{value.toFixed(1)}{isTotal ? '' : '%'}
      </span>
      {showBar && bar(value)}
    </td>
  )
}

export function SuggestionList({ suggestions, draftActive, onRoleChange, onBracketsChange, hasPersonalData, comfortGames = 30 }) {
  const [activeRole, setActiveRole]       = useState('All')
  const [search, setSearch]               = useState('')
  const [sortCol, setSortCol]             = useState('total_score')
  const [sortDir, setSortDir]             = useState('desc')
  const [selectedBrackets, setSelected]   = useState([])  // [] = global

  const handleRole = (role) => {
    setActiveRole(role)
    onRoleChange(role === 'All' ? null : role)
  }

  const toggleBracket = (num) => {
    const next = selectedBrackets.includes(num)
      ? selectedBrackets.filter(b => b !== num)
      : [...selectedBrackets, num]
    setSelected(next)
    onBracketsChange(next.length ? next : null)
  }

  const clearBrackets = () => {
    setSelected([])
    onBracketsChange(null)
  }

  const handleSort = (key) => {
    if (sortCol === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortCol(key)
      setSortDir(key === 'display_name' ? 'asc' : 'desc')
    }
  }

  const visible = useMemo(() => {
    let list = suggestions
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(h => h.display_name.toLowerCase().includes(q))
    }
    return [...list].sort((a, b) => {
      const av = a[sortCol] ?? (sortCol === 'display_name' ? '' : -Infinity)
      const bv = b[sortCol] ?? (sortCol === 'display_name' ? '' : -Infinity)
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [suggestions, search, sortCol, sortDir])

  const visibleCols = COLUMNS.filter(c => !c.personalOnly || hasPersonalData)
  const enemyPickCount = draftActive
    ? (suggestions[0]?.counter_score != null && suggestions.some(h => h.counter_score !== 0) ? 1 : 0)
    : 0

  return (
    <div style={s.container}>
      {/* Toolbar row */}
      <div style={s.toolbar}>
        {/* Role filter */}
        <span style={s.toolbarLabel}>Role</span>
        {ROLES.map(role => (
          <button key={role} style={s.roleBtn(activeRole === role)} onClick={() => handleRole(role)}>{role}</button>
        ))}

        <div style={s.divider} />

        {/* Bracket filter */}
        <span style={s.toolbarLabel} title="Filter win rate data by rank bracket. Select multiple to blend across brackets.">Bracket</span>
        {BRACKETS.map(b => (
          <button
            key={b.num}
            style={s.bracketBtn(selectedBrackets.includes(b.num))}
            onClick={() => toggleBracket(b.num)}
            title={`Include ${b.label} bracket win rates`}
          >
            {b.label}
          </button>
        ))}
        {selectedBrackets.length > 0 && (
          <button style={s.clearBrackets} onClick={clearBrackets} title="Use global (all brackets) win rates">✕ Global</button>
        )}

        {/* Search */}
        <div style={s.searchWrap}>
          <input
            style={s.searchInput} placeholder="Search hero…"
            value={search} onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <span style={{ fontSize: 10, color: 'var(--muted)' }}>{visible.length}/{suggestions.length}</span>
          )}
        </div>
      </div>

      <div style={s.tableWrap}>
        {!draftActive ? (
          <div style={s.waiting}>
            Waiting for draft to start…
            <br />
            <span style={{ fontSize: 11, marginTop: 6, display: 'block' }}>
              Use the <a href="/simulator" target="_blank" style={{ color: 'var(--accent)' }}>Draft Simulator</a> to test without a game.
            </span>
          </div>
        ) : visible.length === 0 ? (
          <div style={s.noData}>
            {search ? `No heroes match "${search}"` : 'No heroes match the current filters.'}
          </div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={{ ...s.th(false), ...s.rank }}>#</th>
                {visibleCols.map(col => (
                  <th
                    key={col.key}
                    style={{ ...s.th(sortCol === col.key), ...(col.right ? s.thRight : {}) }}
                    onClick={() => handleSort(col.key)}
                    title={col.tip}
                  >
                    {col.label}
                    {sortCol === col.key && <SortArrow dir={sortDir} />}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((hero, i) => {
                const name   = hero.hero_name?.replace('npc_dota_hero_', '') || ''
                const imgUrl = `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${name}.png`
                return (
                  <tr key={hero.hero_id} style={s.row(i)}>
                    <td style={{ ...s.td, ...s.rank, ...s.tdRight }}>{i + 1}</td>
                    <td style={s.td}>
                      <div style={s.heroCell}>
                        <img src={imgUrl} alt={hero.display_name} style={s.heroImg}
                          onError={e => { e.target.style.visibility = 'hidden' }} />
                        <div style={s.heroInfo}>
                          <span style={s.heroName}>
                            <span style={s.attrDot(hero.primary_attr)} />
                            {hero.display_name}
                            {hero.personal_games >= comfortGames && (
                              <span
                                style={{ marginLeft: 5, fontSize: 9, color: 'var(--muted)', opacity: 0.8 }}
                                title={`Comfort pick: ${hero.personal_games} games played (${hero.personal_winrate?.toFixed(1)}% win rate)`}
                              >
                                🎮
                              </span>
                            )}
                          </span>
                          <span style={s.heroRoles}>{(hero.roles || []).slice(0, 3).join(' · ')}</span>
                        </div>
                      </div>
                    </td>
                    {visibleCols.slice(1).map(col => {
                      if (col.key === 'personal_winrate') {
                        return (
                          <td key={col.key} style={{ ...s.td, ...s.tdRight }}>
                            {hero.personal_games > 0 ? (
                              <span
                                style={{ color: hero.personal_winrate >= 55 ? 'var(--good)' : hero.personal_winrate >= 45 ? 'var(--muted)' : 'var(--bad)', fontSize: 11 }}
                                title={`${hero.personal_games} games`}
                              >
                                {hero.personal_winrate?.toFixed(1)}%
                                <span style={{ fontSize: 9, color: 'var(--muted)', marginLeft: 2 }}>({hero.personal_games}g)</span>
                              </span>
                            ) : <span style={{ color: 'var(--border)', fontSize: 10 }}>—</span>}
                          </td>
                        )
                      }
                      const showBar = (col.key === 'counter_score' || col.key === 'synergy_score')
                      return <ScoreCell key={col.key} value={hero[col.key]} isTotal={col.isTotal} showBar={showBar} />
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
