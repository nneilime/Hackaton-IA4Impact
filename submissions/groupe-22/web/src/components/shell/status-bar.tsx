import { BatteryFullIcon, SignalIcon, WifiIcon } from "lucide-react"

/** Decorative iOS-like status bar, shown only inside the desktop device frame. */
export function StatusBar() {
  return (
    <div aria-hidden className="relative hidden h-11 shrink-0 items-center justify-between bg-white px-8 pt-1 text-[13px] font-semibold text-navy lg:flex">
      <span className="tabular">9:41</span>
      <div className="absolute left-1/2 top-2 h-7 w-[108px] -translate-x-1/2 rounded-full bg-[#080d34]" />
      <span className="flex items-center gap-1">
        <SignalIcon className="size-3.5" />
        <WifiIcon className="size-3.5" />
        <BatteryFullIcon className="size-4" />
      </span>
    </div>
  )
}
