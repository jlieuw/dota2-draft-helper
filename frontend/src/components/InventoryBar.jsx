const s = {
  root: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 16px',
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
    flexWrap: 'wrap',
  },
  label: { fontSize: 11, color: 'var(--muted)', fontWeight: 600, whiteSpace: 'nowrap' },
  slots: { display: 'flex', gap: 4, flexWrap: 'wrap' },
  slot: {
    width: 40,
    height: 30,
    borderRadius: 3,
    border: '1px solid var(--border)',
    background: 'var(--surface2)',
    overflow: 'hidden',
    position: 'relative',
  },
  img: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' },
  empty: { width: 40, height: 30, borderRadius: 3, border: '1px dashed var(--border)', background: 'var(--surface2)' },
  neutralBadge: {
    position: 'absolute',
    bottom: 1,
    right: 1,
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: 'var(--accent)',
  },
}

const MAIN_SLOTS  = Array.from({ length: 6 }, (_, i) => `slot${i}`)
const STASH_SLOTS = Array.from({ length: 6 }, (_, i) => `stash${i}`)

function ItemSlot({ item, isNeutral = false }) {
  if (!item) return <div style={s.empty} />
  return (
    <div style={s.slot} title={item.item_name.replace(/_/g, ' ')}>
      <img
        style={s.img}
        src={item.image_url || `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/items/${item.item_name}.png`}
        alt={item.item_name}
        onError={e => { e.target.style.display = 'none' }}
      />
      {isNeutral && <div style={s.neutralBadge} title="Neutral item" />}
    </div>
  )
}

export function InventoryBar({ items = [] }) {
  const bySlot = Object.fromEntries(items.map(i => [i.slot, i]))

  return (
    <div style={s.root}>
      <span style={s.label}>Inventory</span>
      <div style={s.slots}>
        {MAIN_SLOTS.map(slot => (
          <ItemSlot key={slot} item={bySlot[slot] ?? null} />
        ))}
      </div>

      <span style={{ ...s.label, marginLeft: 8 }}>Stash</span>
      <div style={s.slots}>
        {STASH_SLOTS.map(slot => (
          <ItemSlot key={slot} item={bySlot[slot] ?? null} />
        ))}
      </div>

      {bySlot['neutral0'] && (
        <>
          <span style={{ ...s.label, marginLeft: 8 }}>Neutral</span>
          <div style={s.slots}>
            <ItemSlot item={bySlot['neutral0']} isNeutral />
          </div>
        </>
      )}
    </div>
  )
}
