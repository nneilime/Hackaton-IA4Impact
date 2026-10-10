// Avis d'enseignants fictifs — données de démonstration (mock). Les noms sont inventés ; reliability.ts tire
// dans cette banque des avis dont la note correspond à l'indice du trajet.
import type { Text } from "./discoveries";

export const TEACHERS: { name: string; role: Text }[] = [
  { name: "Mme Garcia", role: { en: "4th grade teacher", fr: "Professeure des écoles, CM1" } },
  { name: "M. Fabre", role: { en: "History teacher, middle school", fr: "Prof d'histoire-géo, collège" } },
  { name: "Mme Roux", role: { en: "Science teacher, middle school", fr: "Prof de SVT, collège" } },
  { name: "M. Benali", role: { en: "Physics teacher, high school", fr: "Prof de physique-chimie, lycée" } },
  { name: "Mme Vidal", role: { en: "5th grade teacher", fr: "Professeure des écoles, CM2" } },
  { name: "M. Martinez", role: { en: "PE teacher, middle school", fr: "Prof d'EPS, collège" } },
  { name: "Mme Lacombe", role: { en: "Art teacher, high school", fr: "Prof d'arts plastiques, lycée" } },
  { name: "M. Durand", role: { en: "French teacher, middle school", fr: "Prof de français, collège" } },
  { name: "Mme Nguyen", role: { en: "3rd grade teacher", fr: "Professeure des écoles, CE2" } },
  { name: "M. Pujol", role: { en: "Occitan teacher, high school", fr: "Prof d'occitan, lycée" } },
];

// Tranche horaire du départ : un avis qui en porte une ne sort que pour un départ de cette tranche
export type Slot = "morning" | "midday" | "afternoon";
export const slotOf = (minute: number): Slot => (minute < 600 ? "morning" : minute < 810 ? "midday" : "afternoon");

export const REVIEW_BANK: { rating: number[]; needsTransfer?: boolean; direct?: boolean; slot?: Slot; text: Text }[] = [
  {
    rating: [5],
    direct: true,
    text: {
      en: "Direct train, no change: ideal with 25 pupils. We were on time both ways and the controller was very kind to the class.",
      fr: "Train direct, aucune correspondance : idéal avec 25 élèves. À l'heure à l'aller comme au retour, et le contrôleur a été adorable avec la classe.",
    },
  },
  {
    rating: [5, 4],
    text: {
      en: "Booked the group fare three weeks ahead, everything went smoothly. A whole carriage was reserved for us.",
      fr: "Tarif groupe réservé trois semaines avant, tout s'est très bien passé. Une voiture entière nous était réservée.",
    },
  },
  {
    rating: [5, 4],
    text: {
      en: "The kids loved watching the landscape go by. I'd prepared a little quiz on the stations we passed — a hit.",
      fr: "Les enfants ont adoré regarder défiler le paysage. J'avais préparé un petit quiz sur les gares traversées, gros succès.",
    },
  },
  {
    rating: [4],
    text: {
      en: "Reliable overall. Five minutes late on the way back, nothing serious. Plan a margin before the end of the school day.",
      fr: "Fiable dans l'ensemble. Cinq minutes de retard au retour, rien de grave. Prévoyez une marge avant la sortie des classes.",
    },
  },
  {
    rating: [4, 3],
    needsTransfer: true,
    text: {
      en: "The change went fine thanks to the 15-minute margin, but counting 28 pupils on a platform is stressful. Assign one adult per group.",
      fr: "La correspondance s'est bien passée grâce aux 15 minutes de marge, mais compter 28 élèves sur un quai, c'est stressant. Un adulte par groupe.",
    },
  },
  {
    rating: [4],
    text: {
      en: "Clean, quiet train in the morning. On the way back it was busier, we had to split the class across two carriages.",
      fr: "Train propre et calme le matin. Au retour c'était plus chargé, on a dû répartir la classe sur deux voitures.",
    },
  },
  {
    rating: [3],
    text: {
      en: "Average. 12 minutes late on the way there, so we cut the guided tour short. The return was on time.",
      fr: "Mitigé. 12 minutes de retard à l'aller, on a dû raccourcir la visite guidée. Le retour était à l'heure.",
    },
  },
  {
    rating: [3, 2],
    needsTransfer: true,
    text: {
      en: "We missed the connection by two minutes and waited almost an hour for the next one. Parents were waiting at school…",
      fr: "Correspondance ratée à deux minutes près, presque une heure d'attente pour le suivant. Les parents attendaient devant l'école…",
    },
  },
  {
    rating: [3],
    text: {
      en: "Fine, but the station has no shelter for a group: in the rain with 30 children it's long. Bring raincoats.",
      fr: "Correct, mais la gare n'a pas d'abri pour un groupe : sous la pluie avec 30 enfants, c'est long. Prévoyez les K-way.",
    },
  },
  {
    rating: [2],
    text: {
      en: "Train cancelled the day before, replaced by a coach. SNCF warned us in time but we had to redo the whole schedule.",
      fr: "Train supprimé la veille, remplacé par un car. La SNCF nous a prévenus à temps mais il a fallu refaire tout le planning.",
    },
  },
  {
    rating: [2, 1],
    text: {
      en: "40 minutes late on the return, no information on the platform. I wouldn't do it again on a Friday afternoon.",
      fr: "40 minutes de retard au retour, aucune info sur le quai. Je ne le referai pas un vendredi après-midi.",
    },
  },
  {
    rating: [5, 4],
    text: {
      en: "Third year we've done this outing. Never a problem, and it costs far less than chartering a coach.",
      fr: "Troisième année qu'on fait cette sortie. Jamais de souci, et bien moins cher que d'affréter un car.",
    },
  },
  {
    rating: [4, 3],
    text: {
      en: "Good trip. Tip: the front of the train is emptier, gather the class at the head of the platform.",
      fr: "Bon trajet. Astuce : l'avant du train est plus vide, regroupez la classe en tête de quai.",
    },
  },
  // — Avis liés à l'heure du départ —
  {
    rating: [3, 2],
    slot: "morning",
    text: {
      en: "The morning train is packed with commuters and high-schoolers: half the class stood until the third stop.",
      fr: "Le train du matin est bondé d'actifs et de lycéens : la moitié de la classe est restée debout jusqu'au troisième arrêt.",
    },
  },
  {
    rating: [4, 3],
    slot: "morning",
    text: {
      en: "Early departure, so the meeting point was at 7:30. A few late pupils made it stressful, but we arrived for the opening.",
      fr: "Départ tôt, rendez-vous à 7 h 30 en gare. Quelques retardataires, un peu stressant, mais on est arrivés pour l'ouverture.",
    },
  },
  {
    rating: [5, 4],
    slot: "morning",
    text: {
      en: "Leaving in the morning gives the whole day on site. Train slightly late, but nothing compared to the time gained.",
      fr: "Partir le matin laisse toute la journée sur place. Léger retard, mais rien à côté du temps gagné.",
    },
  },
  {
    rating: [5],
    slot: "midday",
    text: {
      en: "Off-peak train, almost empty: the class sat together in one carriage. The calmest trip I've done with pupils.",
      fr: "Train de milieu de journée presque vide : toute la classe assise dans la même voiture. Le trajet le plus calme que j'ai fait avec des élèves.",
    },
  },
  {
    rating: [4, 5],
    slot: "midday",
    text: {
      en: "Late-morning departure, no rush and on time. Only downside: a shorter visit, plan a half-day activity.",
      fr: "Départ en fin de matinée, sans bousculade et à l'heure. Seul bémol : visite plus courte, prévoyez une activité d'une demi-journée.",
    },
  },
  {
    rating: [3, 4],
    slot: "midday",
    text: {
      en: "Fewer trains around noon: if you miss one, the next is far. We were on time, but I wouldn't cut it close.",
      fr: "Moins de trains autour de midi : si on en rate un, le suivant est loin. On était à l'heure, mais je ne prendrais pas de marge serrée.",
    },
  },
  {
    rating: [2, 3],
    slot: "afternoon",
    text: {
      en: "Afternoon train full of high-schoolers going home. Impossible to keep the group together, and 15 minutes late.",
      fr: "Train de l'après-midi rempli de lycéens qui rentrent. Impossible de garder le groupe ensemble, et 15 minutes de retard.",
    },
  },
  {
    rating: [3],
    slot: "afternoon",
    text: {
      en: "We arrived after 3 p.m.: some sites close early. Check opening hours, we only had an hour on site.",
      fr: "Arrivée après 15 h : certains sites ferment tôt. Vérifiez les horaires, on n'a eu qu'une heure sur place.",
    },
  },
  {
    rating: [4],
    slot: "afternoon",
    text: {
      en: "Good choice for a short visit in the afternoon. Busier on board than in the morning, but the controller helped us.",
      fr: "Bon choix pour une visite courte l'après-midi. Plus de monde qu'au matin, mais le contrôleur nous a aidés à nous placer.",
    },
  },
];
