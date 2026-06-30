import { useEffect, useRef } from 'react'

export function useKeyboardShortcuts(shortcuts) {
  const shortcutsRef = useRef(shortcuts)
  shortcutsRef.current = shortcuts

  useEffect(() => {
    const handler = (e) => {
      const current = shortcutsRef.current
      const isInput = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT'
      const key = e.key.toLowerCase()

      for (const s of current) {
        if (s.ctrl && !(e.ctrlKey || e.metaKey)) continue
        if (!s.ctrl && (e.ctrlKey || e.metaKey)) continue

        const keyMatch = Array.isArray(s.key)
          ? s.key.includes(key)
          : s.key === key

        if (!keyMatch) continue

        if (isInput && !s.allowInput) continue

        e.preventDefault()
        s.handler(e)
        return
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
}
