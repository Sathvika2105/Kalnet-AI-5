import { useEffect, useRef } from 'react'

export function useKeyboardShortcuts(shortcuts) {
  const shortcutsRef = useRef(shortcuts)
  shortcutsRef.current = shortcuts

  useEffect(() => {
    const handler = (e) => {
      const current = shortcutsRef.current

      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        for (const s of current) {
          if (s.ctrl !== undefined) {
            if (e.ctrlKey || e.metaKey) {
              const key = e.key.toLowerCase()
              if ((Array.isArray(s.key) ? s.key : [s.key]).includes(key)) {
                if (s.ctrl !== false) continue
              }
            }
          }
        }
      }

      for (const s of current) {
        const mod = s.ctrl ? (e.ctrlKey || e.metaKey) : true
        const keyMatch = Array.isArray(s.key)
          ? s.key.includes(e.key.toLowerCase())
          : e.key.toLowerCase() === s.key

        if (mod && keyMatch && !e.ctrlKey !== !s.ctrl) continue

        if (mod && keyMatch) {
          if (!s.allowInput && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) {
            continue
          }
          e.preventDefault()
          s.handler(e)
          return
        }
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
}
