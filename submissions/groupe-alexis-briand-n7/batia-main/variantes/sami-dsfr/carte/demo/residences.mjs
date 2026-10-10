// Les huit résidences d'Assise : positions fictives (serveur.mjs d'Assise), comptages calculés par Assise
// sur les données fictives du kit BâtIA au 31/12/2025. aVisiter : logements dont un équipement est prioritaire ;
// aSurveiller : logements dont le plus haut niveau est « à surveiller » ; communsAVisiter : équipements communs prioritaires.
export const RESIDENCES = [
  { id: 'RES-A', nom: 'Résidence A', lettre: 'A', position: [43.646, 1.392], logements: 160, aVisiter: 1, aSurveiller: 11, communsAVisiter: 0 },
  { id: 'RES-B', nom: 'Résidence B', lettre: 'B', position: [43.668, 1.447], logements: 60, aVisiter: 5, aSurveiller: 13, communsAVisiter: 0 },
  { id: 'RES-C', nom: 'Résidence C', lettre: 'C', position: [43.618, 1.486], logements: 230, aVisiter: 0, aSurveiller: 0, communsAVisiter: 1 },
  { id: 'RES-D', nom: 'Résidence D', lettre: 'D', position: [43.566, 1.398], logements: 100, aVisiter: 16, aSurveiller: 26, communsAVisiter: 0 },
  { id: 'RES-E', nom: 'Résidence E', lettre: 'E', position: [43.584, 1.522], logements: 140, aVisiter: 3, aSurveiller: 26, communsAVisiter: 0 },
  { id: 'RES-F', nom: 'Résidence F', lettre: 'F', position: [43.652, 1.503], logements: 150, aVisiter: 9, aSurveiller: 20, communsAVisiter: 1 },
  { id: 'RES-G', nom: 'Résidence G', lettre: 'G', position: [43.574, 1.452], logements: 170, aVisiter: 2, aSurveiller: 30, communsAVisiter: 0 },
  { id: 'RES-H', nom: 'Résidence H', lettre: 'H', position: [43.617, 1.346], logements: 90, aVisiter: 3, aSurveiller: 25, communsAVisiter: 0 },
];
