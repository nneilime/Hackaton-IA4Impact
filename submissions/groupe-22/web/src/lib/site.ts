// The app's own texts about the assistant: no figures here (rates, fees, delays, phone
// numbers), the assistant gives them from the bank's procedure sheets (bank_docs/), so
// they can't drift apart.

export interface Topic {
  id: string // the procedure sheet (bank_docs/<id>.md)
  title: string
  text: string
  question: string // asked to Compass when tapped
}

export const TOPICS: Topic[] = [
  {
    id: "code_perdu",
    title: "Carte ou code perdu",
    text: "Opposition avec votre accord, code oublié, mot de passe.",
    question: "J'ai perdu ma carte bancaire",
  },
  {
    id: "credit",
    title: "Simuler un crédit",
    text: "Cinq questions, une simulation sans engagement.",
    question: "Je voudrais simuler un crédit",
  },
  {
    id: "reclamation",
    title: "Faire une réclamation",
    text: "Frais, prélèvement, opération inconnue.",
    question: "Je voudrais faire une réclamation",
  },
  {
    id: "gestion_privee",
    title: "Épargne et patrimoine",
    text: "Livrets, assurance vie, gestion privée.",
    question: "Quelle épargne pour mettre de côté ?",
  },
]

// Under the greeting of a new written conversation, for a logged-in customer.
export const SUGGESTIONS = [
  "Quel est mon solde ?",
  "J'ai perdu ma carte",
  "Je ne reconnais pas un paiement de 89 euros",
  "Simuler un crédit",
  "Faire une réclamation",
  "Parler à un conseiller",
]

// The public home's questions, and a visitor's new conversation: nothing that needs an
// account, except the one that shows the Connexion démo.
export const PUBLIC_SUGGESTIONS = [
  "Je souhaite simuler un crédit.",
  "J'ai oublié mon mot de passe.",
  "Je veux faire une réclamation.",
  "Je voudrais parler à un conseiller.",
  "Comment ouvrir un compte ?",
]
