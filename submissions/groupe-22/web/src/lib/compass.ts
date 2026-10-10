import { sendChat } from "./chat"
import { usePrefs } from "./prefs"
import { useCompass } from "./store"
import { sendVoiceText, voiceActive } from "./voice"

/** Opens Compass with a question already asked (the app's « Demander à Compass »
 * buttons): in the call if there is one, otherwise in writing. */
export function askCompass(message: string) {
  if (voiceActive()) {
    useCompass.setState({ sheet: "open", voice: true })
    sendVoiceText(message)
    return
  }
  useCompass.setState({ sheet: "open", voice: false })
  sendChat(message)
}

/** Opens Compass: by voice or in writing (by default, as set in Profil). A call in
 * progress is always what it shows. */
export function openCompass(mode = usePrefs.getState().mode) {
  useCompass.setState({ sheet: "open", voice: voiceActive() || mode === "voice" })
}

/** The buttons of an action Compass prepared: the customer's answer, said in the
 * conversation it belongs to, as if typed or spoken. The server only does the action
 * after this turn (bank_tools.Conversation.confirm). */
export function answerAction(via: "text" | "voice", yes: boolean) {
  const text = yes ? "Oui, je confirme." : "Non, j'annule."
  if (via === "voice") sendVoiceText(text)
  else sendChat(text)
}
