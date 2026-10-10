import { useEffect } from "react"
import { useCompass } from "@/lib/store"
import type { AppPage } from "@/lib/types"

/** Each screen declares itself: Compass's header shows where the customer is. */
export function usePage(page: AppPage) {
  useEffect(() => {
    useCompass.setState({ page })
  }, [page])
}
