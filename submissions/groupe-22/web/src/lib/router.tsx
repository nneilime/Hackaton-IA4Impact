import { useSyncExternalStore, type AnchorHTMLAttributes } from "react"

// A tiny router over the History API: the app's few pages don't need more. The server
// answers every page path with index.html (PageFiles in server.py).

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  window.addEventListener("popstate", listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener("popstate", listener)
  }
}

const currentHref = () => location.pathname + location.search

/** The current path and query, re-rendering on every navigation. */
export function useLocation() {
  const href = useSyncExternalStore(subscribe, currentHref)
  const url = new URL(href, location.origin)
  return { pathname: url.pathname, params: url.searchParams }
}

export function navigate(href: string, { replace = false } = {}) {
  if (href === currentHref()) return
  history[replace ? "replaceState" : "pushState"](null, "", href)
  listeners.forEach((listener) => listener())
}

export function back(fallback = "/") {
  if (history.length > 1) history.back()
  else navigate(fallback)
}

/** A link that navigates without reloading the page (a new tab still works). */
export function Link({ href, onClick, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  return (
    <a
      href={href}
      onClick={(e) => {
        onClick?.(e)
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
        e.preventDefault()
        navigate(href)
      }}
      {...rest}
    />
  )
}
