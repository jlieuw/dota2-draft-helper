import React from 'react'

const s = {
  panel: {
    padding: '16px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    overflowY: 'auto',
    flex: 1,
  },
  heading: {
    fontSize: 12,
    fontWeight: 700,
    color: 'var(--muted)',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  row: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  card: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 5,
    padding: '5px 8px',
    minWidth: 140,
  },
  portrait: {
    width: 46,
    height: 26,
    objectFit: 'cover',
    borderRadius: 2,
    background: 'var(--surface2)',
    flexShrink: 0,
  },
  info: {
    display: 'flex',
    flexDirection: 'column',
    gap: 1,
    minWidth: 0,
  },
  name: {
    fontSize: 11,
    fontWeight: 500,
    color: 'var(--text)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  stats: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    fontSize: 10,
  },
  wr: (wr) => ({
    fontWeight: 600,
    color: wr >= 55 ? 'var(--good)' : wr < 45 ? 'var(--bad)' : 'var(--muted)',
  }),
  games: {
    color: 'var(--muted)',
  },
  empty: {
    color: 'var(--muted)',
    fontSize: 12,
    padding: '6px 0',
  },
  titleRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 8,
  },
  subtitle: {
    fontSize: 10,
    color: 'var(--border)',
  },
}

function HeroCard({ hero }) {
  const name = hero.hero_name?.replace('npc_dota_hero_', '') || ''
  const imgUrl = name
    ? `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${name}.png`
    : ''

  return (
    <div style={s.card}>
      {imgUrl && (
        <img
          src={imgUrl}
          alt={hero.display_name}
          style={s.portrait}
          onError={e => { e.target.style.display = 'none' }}
        />
      )}
      <div style={s.info}>
        <span style={s.name}>{hero.display_name}</span>
        <div style={s.stats}>
          <span style={s.wr(hero.win_rate)}>{hero.win_rate.toFixed(1)}%</span>
          <span style={s.games}>{hero.games}g</span>
        </div>
      </div>
    </div>
  )
}

function Section({ title, subtitle, heroes }) {
  return (
    <div style={s.section}>
      <div style={s.titleRow}>
        <span style={s.heading}>{title}</span>
        {subtitle && <span style={s.subtitle}>{subtitle}</span>}
      </div>
      {heroes.length === 0 ? (
        <span style={s.empty}>No data yet</span>
      ) : (
        <div style={s.row}>
          {heroes.map(h => <HeroCard key={h.hero_id} hero={h} />)}
        </div>
      )}
    </div>
  )
}

export function MyHeroesPanel({ summary }) {
  if (!summary) return null

  return (
    <div style={s.panel}>
      <Section
        title="Most Played"
        subtitle={`${summary.total_heroes_played} heroes total`}
        heroes={summary.most_played}
      />
      <Section
        title="Best Win Rate"
        subtitle="min 20 games"
        heroes={summary.best_winrate}
      />
      <Section
        title="Worst Win Rate"
        subtitle="min 20 games"
        heroes={summary.worst_winrate}
      />
    </div>
  )
}
