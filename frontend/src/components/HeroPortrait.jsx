import React from 'react'

const styles = {
  wrap: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 3,
  },
  img: {
    width: 48,
    height: 27,
    objectFit: 'cover',
    borderRadius: 3,
    border: '1px solid var(--border)',
    background: 'var(--surface2)',
  },
  empty: {
    width: 48,
    height: 27,
    borderRadius: 3,
    border: '1px dashed var(--border)',
    background: 'var(--surface2)',
  },
  name: {
    fontSize: 9,
    color: 'var(--muted)',
    textAlign: 'center',
    maxWidth: 52,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
}

export function HeroPortrait({ hero, size = 'sm' }) {
  if (!hero) {
    return (
      <div style={styles.wrap}>
        <div style={styles.empty} />
      </div>
    )
  }

  const internalName = hero.name?.replace('npc_dota_hero_', '') || ''
  const imgUrl = `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${internalName}.png`

  return (
    <div style={styles.wrap} title={hero.name}>
      <img
        src={imgUrl}
        alt={hero.name}
        style={styles.img}
        onError={(e) => { e.target.style.display = 'none' }}
      />
      <span style={styles.name}>{internalName.replace(/_/g, ' ')}</span>
    </div>
  )
}
