import { useState } from 'react'

const PHASE_LABELS = { start: 'OPENING', early: 'EARLY', mid: 'MID', late: 'LATE' }
const PHASE_COLORS = {
  start: 'var(--muted)',
  early: '#4fc3f7',
  mid:   'var(--accent)',
  late:  '#ef9a9a',
}

const s = {
  root: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },

  toolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '6px 16px',
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
    flexWrap: 'wrap',
  },
  toolbarLabel: { fontSize: 11, color: 'var(--muted)', fontWeight: 600 },

  filterGroup: { display: 'flex', gap: 4 },
  filterBtn: (active) => ({
    padding: '3px 10px',
    borderRadius: 4,
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    background: active ? 'rgba(240,165,0,0.12)' : 'transparent',
    color: active ? 'var(--accent)' : 'var(--muted)',
    fontSize: 11, fontWeight: active ? 600 : 400,
    cursor: 'pointer', fontFamily: 'inherit',
    transition: 'all 0.12s',
  }),

  affordToggle: (active) => ({
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '3px 10px', borderRadius: 4,
    border: `1px solid ${active ? 'var(--good)' : 'var(--border)'}`,
    background: active ? 'rgba(63,185,80,0.1)' : 'transparent',
    color: active ? 'var(--good)' : 'var(--muted)',
    fontSize: 11, cursor: 'pointer', fontFamily: 'inherit',
    transition: 'all 0.12s',
  }),

  table: { flex: 1, overflowY: 'auto' },
  tableInner: { width: '100%', borderCollapse: 'collapse' },

  th: {
    position: 'sticky', top: 0,
    padding: '6px 10px',
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    fontSize: 10, fontWeight: 600,
    color: 'var(--muted)', textAlign: 'left',
    whiteSpace: 'nowrap', cursor: 'pointer',
    userSelect: 'none',
  },
  thRight: { textAlign: 'right' },

  row: (afford, component) => ({
    borderBottom: '1px solid var(--border)',
    opacity: afford ? 1 : 0.55,
    background: component ? 'rgba(240,165,0,0.04)' : 'transparent',
    transition: 'background 0.1s',
  }),

  tdImg: { padding: '4px 6px 4px 10px', width: 44 },
  itemImg: { width: 40, height: 30, objectFit: 'cover', borderRadius: 3, display: 'block' },
  itemImgFallback: { width: 40, height: 30, borderRadius: 3, background: 'var(--surface2)', display: 'block' },

  tdName: { padding: '4px 8px' },
  itemName: { fontSize: 13, fontWeight: 500, color: 'var(--text)' },
  itemMeta: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 },
  phaseBadge: (phase) => ({
    fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
    padding: '1px 5px', borderRadius: 3,
    background: `${PHASE_COLORS[phase]}22`,
    color: PHASE_COLORS[phase],
    border: `1px solid ${PHASE_COLORS[phase]}44`,
  }),
  reason: { fontSize: 10, color: 'var(--accent)', fontStyle: 'italic' },
  componentBadge: { fontSize: 9, color: 'var(--good)', fontWeight: 600 },

  tdNum: { padding: '4px 10px', textAlign: 'right', fontSize: 12, whiteSpace: 'nowrap' },
  gold: { color: 'var(--accent)', fontWeight: 600 },
  goldCant: { color: 'var(--muted)' },
  winRate: { color: 'var(--text)' },

  scoreBar: { display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' },
  barTrack: { width: 60, height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' },
  barFill: (pct) => ({
    height: '100%',
    width: `${pct}%`,
    borderRadius: 2,
    background: pct >= 70 ? 'var(--good)' : pct >= 45 ? 'var(--accent)' : 'var(--muted)',
    transition: 'width 0.3s ease',
  }),
  scoreNum: { fontSize: 12, fontWeight: 600, color: 'var(--text)', minWidth: 28, textAlign: 'right' },

  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flex: 1, color: 'var(--muted)', fontSize: 13,
  },
}

const SORT_OPTIONS = [
  { key: 'total_score', label: 'Score' },
  { key: 'win_rate',    label: 'Win rate' },
  { key: 'cost',        label: 'Cost' },
]

const PHASE_FILTERS = ['all', 'start', 'early', 'mid', 'late']

export function ItemSuggestionList({ items = [], gold = 0 }) {
  const [sortKey, setSortKey]         = useState('total_score')
  const [sortAsc, setSortAsc]         = useState(false)
  const [phaseFilter, setPhaseFilter] = useState('all')
  const [affordOnly, setAffordOnly]   = useState(false)

  function toggleSort(key) {
    if (sortKey === key) setSortAsc(v => !v)
    else { setSortKey(key); setSortAsc(false) }
  }

  const filtered = items
    .filter(i => phaseFilter === 'all' || i.phase === phaseFilter)
    .filter(i => !affordOnly || i.can_afford)

  const sorted = [...filtered].sort((a, b) => {
    const diff = (a[sortKey] ?? 0) - (b[sortKey] ?? 0)
    return sortAsc ? diff : -diff
  })

  function ColHeader({ k, label, right = false }) {
    const active = sortKey === k
    return (
      <th
        style={{ ...s.th, ...(right ? s.thRight : {}), color: active ? 'var(--text)' : 'var(--muted)' }}
        onClick={() => toggleSort(k)}
      >
        {label} {active ? (sortAsc ? '↑' : '↓') : ''}
      </th>
    )
  }

  return (
    <div style={s.root}>
      <div style={s.toolbar}>
        <span style={s.toolbarLabel}>Phase</span>
        <div style={s.filterGroup}>
          {PHASE_FILTERS.map(p => (
            <button key={p} style={s.filterBtn(phaseFilter === p)} onClick={() => setPhaseFilter(p)}>
              {p === 'all' ? 'All' : PHASE_LABELS[p]}
            </button>
          ))}
        </div>

        <button style={s.affordToggle(affordOnly)} onClick={() => setAffordOnly(v => !v)}>
          {affordOnly ? '✓ ' : ''}Can afford
        </button>

        <span style={{ ...s.toolbarLabel, marginLeft: 'auto', color: 'var(--accent)' }}>
          🪙 {gold.toLocaleString()} gold
        </span>
      </div>

      {sorted.length === 0 ? (
        <div style={s.empty}>
          {items.length === 0
            ? 'Loading item data for this hero…'
            : 'No items match the current filters.'}
        </div>
      ) : (
        <div style={s.table}>
          <table style={s.tableInner}>
            <thead>
              <tr>
                <th style={s.th} colSpan={2}>Item</th>
                <ColHeader k="cost"        label="Cost"    right />
                <ColHeader k="win_rate"    label="Win rate" right />
                <ColHeader k="total_score" label="Score"   right />
              </tr>
            </thead>
            <tbody>
              {sorted.map(item => (
                <tr key={item.item_name} style={s.row(item.can_afford, item.has_component)}>
                  <td style={s.tdImg}>
                    <img
                      style={s.itemImg}
                      src={item.image_url}
                      alt={item.display_name}
                      onError={e => { e.target.style.display = 'none' }}
                    />
                  </td>

                  <td style={s.tdName}>
                    <div style={s.itemName}>{item.display_name}</div>
                    <div style={s.itemMeta}>
                      <span style={s.phaseBadge(item.phase)}>{PHASE_LABELS[item.phase]}</span>
                      {item.reason && <span style={s.reason}>{item.reason}</span>}
                      {item.has_component && <span style={s.componentBadge}>▲ component owned</span>}
                    </div>
                  </td>

                  <td style={s.tdNum}>
                    <span style={item.can_afford ? s.gold : s.goldCant}>
                      🪙 {item.cost.toLocaleString()}
                    </span>
                  </td>

                  <td style={s.tdNum}>
                    <span style={s.winRate}>{item.win_rate}%</span>
                    <div style={{ fontSize: 9, color: 'var(--muted)' }}>
                      {(item.games / 1000).toFixed(1)}k games
                    </div>
                  </td>

                  <td style={s.tdNum}>
                    <div style={s.scoreBar}>
                      <div style={s.barTrack}>
                        <div style={s.barFill(item.total_score)} />
                      </div>
                      <span style={s.scoreNum}>{item.total_score}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
