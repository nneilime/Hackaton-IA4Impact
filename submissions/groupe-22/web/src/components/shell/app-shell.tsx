import { useEffect, useRef } from "react"
import { MotionConfig } from "motion/react"
import { useAuth } from "@/lib/auth"
import { usePrefs } from "@/lib/prefs"
import { useLocation } from "@/lib/router"
import { BottomNav } from "./bottom-nav"
import { StatusBar } from "./status-bar"
import { Toaster } from "./toast"
import { CompassLayer } from "@/components/compass/compass-layer"
import { DemoPanel } from "@/components/demo/demo-panel"
import { BrandColumn } from "./brand-column"
import { LoginDialog } from "@/components/auth/login-dialog"

/** Applies the accessibility preferences (Profil) to the whole document. */
function PreferencesApplier() {
  const { textScale, highContrast, reducedMotion } = usePrefs()
  useEffect(() => {
    const root = document.documentElement
    root.style.fontSize = `${16 * textScale}px`
    root.dataset.contrast = highContrast ? "high" : "normal"
    const systemReduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    root.dataset.motion = reducedMotion || systemReduce ? "reduce" : "full"
  }, [textScale, highContrast, reducedMotion])
  return null
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const reduce = usePrefs((p) => p.reducedMotion)
  const customer = useAuth((s) => s.status === "customer") // the bank's menu: once logged in

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 })
  }, [pathname])

  return (
    <MotionConfig reducedMotion={reduce ? "always" : "user"}>
      <PreferencesApplier />
      <div className="stage-bg flex min-h-[100dvh] items-stretch justify-center lg:items-center lg:gap-8 lg:px-6 lg:py-5">
        <BrandColumn />
        {/* Phone: full screen on mobile, framed device on desktop */}
        <div className="relative w-full lg:w-auto">
          <div className="relative mx-auto h-[100dvh] w-full overflow-hidden bg-white lg:h-[min(844px,calc(100dvh-40px))] lg:w-[390px] lg:rounded-[54px] lg:shadow-[0_0_0_11px_#080d34,0_0_0_13px_#424d77,0_40px_80px_-20px_rgba(8,13,52,0.45)]">
            <div id="app-viewport" className="relative flex h-full flex-col overflow-hidden bg-white">
              <a
                href="#main"
                className="sr-only z-[90] rounded-lg bg-navy px-3 py-2 text-white focus:not-sr-only focus:absolute focus:left-3 focus:top-3"
              >
                Aller au contenu
              </a>
              <StatusBar />
              <main id="main" ref={mainRef} tabIndex={-1} className="no-scrollbar relative flex-1 overflow-y-auto overscroll-contain bg-surface outline-none">
                {children}
              </main>
              {customer && <BottomNav />}
              <CompassLayer />
              <LoginDialog />
              <Toaster />
            </div>
          </div>
        </div>
        <DemoPanel />
      </div>
    </MotionConfig>
  )
}
