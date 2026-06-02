import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `ws://${window.location.hostname}:4000/ws`

export function useWebSocket() {
  const [data, setData]         = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef     = useRef(null)
  const filterRef = useRef({ role_filter: null, brackets: null })

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      // Re-send filters on reconnect
      const f = filterRef.current
      if (f.role_filter || f.brackets) {
        ws.send(JSON.stringify(f))
      }
    }
    ws.onmessage = (e) => {
      try { setData(JSON.parse(e.data)) } catch {}
    }
    ws.onclose = () => {
      setConnected(false)
      setTimeout(connect, 2000)
    }
    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  const sendFilters = useCallback((updates) => {
    filterRef.current = { ...filterRef.current, ...updates }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(filterRef.current))
    }
  }, [])

  const setRoleFilter = useCallback((role) => {
    sendFilters({ role_filter: role || null })
  }, [sendFilters])

  const setBrackets = useCallback((brackets) => {
    // brackets: array of ints e.g. [3,4,5] or null for global
    sendFilters({ brackets: brackets && brackets.length ? brackets : null })
  }, [sendFilters])

  return { data, connected, setRoleFilter, setBrackets }
}
