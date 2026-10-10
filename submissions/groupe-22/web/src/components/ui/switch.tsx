import { cn } from "@/lib/utils"

/** An on/off switch: a button with role="switch", read as such by screen readers. */
export function Switch({ checked, onCheckedChange, className, ...rest }: { checked: boolean; onCheckedChange: (checked: boolean) => void } & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange">) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-[26px] w-[44px] shrink-0 items-center rounded-full transition-colors after:absolute after:-inset-x-2 after:-inset-y-3",
        checked ? "bg-ok" : "bg-[#acacac]",
        className,
      )}
      {...rest}
    >
      <span className={cn("block size-[22px] rounded-full bg-white shadow transition-transform", checked ? "translate-x-[20px]" : "translate-x-[2px]")} />
    </button>
  )
}
