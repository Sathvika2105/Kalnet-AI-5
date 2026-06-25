import { useEffect } from 'react'

export function useKeyboardShortcuts(shortcuts) {
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        for (const s of shortcuts) {
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

      for (const s of shortcuts) {
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
  }, [shortcuts])
}