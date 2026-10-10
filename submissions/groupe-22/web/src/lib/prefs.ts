import { create } from "zustand"
import type { Mode } from "./types"

// The visitor's display and assistant preferences, remembered on this device.
export interface Preferences {
  textScale: 1 | 1.15 | 1.3
  highContrast: boolean
  reducedMotion: boolean
  voice: "marin" | "cedar" // the assistant's voice on the next call (server.py VOICES)
  pushToTalk: boolean // noisy room: « Parler » then « Envoyer », no voice detection
  mode: Mode // what the Compass button opens
  simple: boolean // Compass explains in short sentences and everyday words
}

const DEFAULTS: Preferences = {
  textScale: 1,
  highContrast: false,
  reducedMotion: false,
  voice: "marin",
  pushToTalk: false,
  mode: "text",
  simple: false,
}

function load(): Preferences {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem("preferences") ?? "{}") }
  } catch {
    return DEFAULTS // private browsing, or storage blocked
  }
}

export const usePrefs = create<Preferences>(load)

export function savePrefs(change: Partial<Preferences>) {
  usePrefs.setState(change)
  try {
    localStorage.setItem("preferences", JSON.stringify(usePrefs.getState()))
  } catch {
    /* not remembered */
  }
}
