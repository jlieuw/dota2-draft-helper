import { InventoryBar } from './InventoryBar'
import { ItemSuggestionList } from './ItemSuggestionList'

const s = {
  root: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },

  heroHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '8px 16px',
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
  },
  heroImg: { width: 64, height: 36, objectFit: 'cover', borderRadius: 4, flexShrink: 0 },
  heroInfo: { display: 'flex', flexDirection: 'column', gap: 2 },
  heroName: { fontSize: 14, fontWeight: 700, color: 'var(--text)', textTransform: 'capitalize' },
  heroMeta: { display: 'flex', gap: 12, fontSize: 11, color: 'var(--muted)' },
  metaItem: { display: 'flex', gap: 4, alignItems: 'center' },
  metaValue: { color: 'var(--text)', fontWeight: 500 },

  allyEnemy: { marginLeft: 'auto', display: 'flex', gap: 16, alignItems: 'center' },
  teamGroup: { display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-end' },
  teamLabel: { fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' },
  teamHeroes: { display: 'flex', gap: 3 },
  miniHero: {
    width: 28, height: 16, objectFit: 'cover',
    borderRadius: 2, border: '1px solid transparent',
  },

  noData: {
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    flex: 1, gap: 8, color: 'var(--muted)', fontSize: 13,
  },
  noDataHint: { fontSize: 11, color: 'var(--border)', maxWidth: 340, textAlign: 'center', lineHeight: 1.6 },
}

function MiniHero({ name, color }) {
  const url = `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${name}.png`
  return (
    <img
      style={{ ...s.miniHero, borderColor: color }}
      src={url}
      alt={name}
      title={name.replace(/_/g, ' ')}
      onError={e => { e.target.style.display = 'none' }}
    />
  )
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function InGamePanel({ gameState, itemSuggestions }) {
  if (!gameState?.active) {
    return (
      <div style={s.noData}>
        <span>⚔️ Waiting for a game…</span>
        <span style={s.noDataHint}>
          Item suggestions appear automatically once Dota 2 sends in-game data.
          Make sure you've re-run <code>setup_gsi.py</code> to enable the new GSI keys.
        </span>
      </div>
    )
  }

  const heroImgUrl = `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${gameState.hero_name}.png`
  const heroDisplay = gameState.hero_name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  return (
    <div style={s.root}>
      {/* Hero + match context header */}
      <div style={s.heroHeader}>
        <img
          style={s.heroImg}
          src={heroImgUrl}
          alt={heroDisplay}
          onError={e => { e.target.style.display = 'none' }}
        />
        <div style={s.heroInfo}>
          <div style={s.heroName}>{heroDisplay}</div>
          <div style={s.heroMeta}>
            <span style={s.metaItem}>
              Lvl <span style={s.metaValue}>{gameState.hero_level}</span>
            </span>
            <span style={s.metaItem}>
              🕐 <span style={s.metaValue}>{formatTime(gameState.game_time)}</span>
            </span>
            <span style={s.metaItem}>
              🪙 <span style={{ ...s.metaValue, color: 'var(--accent)' }}>
                {gameState.gold.toLocaleString()}
              </span>
            </span>
            <span style={s.metaItem}>
              Net worth <span style={s.metaValue}>{gameState.net_worth.toLocaleString()}</span>
            </span>
          </div>
        </div>

        {/* Ally / enemy lineup */}
        {(gameState.ally_hero_names?.length > 0 || gameState.enemy_hero_names?.length > 0) && (
          <div style={s.allyEnemy}>
            {gameState.ally_hero_names?.length > 0 && (
              <div style={s.teamGroup}>
                <span style={{ ...s.teamLabel, color: 'var(--radiant)' }}>Allies</span>
                <div style={s.teamHeroes}>
                  {gameState.ally_hero_names.map(h => (
                    <MiniHero key={h} name={h} color="var(--radiant)" />
                  ))}
                </div>
              </div>
            )}
            {gameState.enemy_hero_names?.length > 0 && (
              <div style={s.teamGroup}>
                <span style={{ ...s.teamLabel, color: 'var(--dire)' }}>Enemies</span>
                <div style={s.teamHeroes}>
                  {gameState.enemy_hero_names.map(h => (
                    <MiniHero key={h} name={h} color="var(--dire)" />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Current inventory */}
      <InventoryBar items={gameState.items ?? []} />

      {/* Ranked item suggestions */}
      <ItemSuggestionList items={itemSuggestions ?? []} gold={gameState.gold} />
    </div>
  )
}
