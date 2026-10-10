import { Route, Routes } from 'react-router-dom'
import AppShell from './layout/AppShell'
import Accueil from './pages/Accueil'
import Comparer from './pages/Comparer'
import Destinations from './pages/Destinations'
import Dossier from './pages/Dossier'
import PageIntrouvable from './pages/PageIntrouvable'
import PreReservation from './pages/PreReservation'
import Retour from './pages/Retour'
import ScenePage from './scene/ScenePage'
import Trajets from './pages/Trajets'
import VoteAnimer from './pages/VoteAnimer'
import VoteEleve from './pages/VoteEleve'

export default function App() {
  return (
    <Routes>
      {/* Nouvelle entrée : la scène Tchouette, hors du shell classique. */}
      <Route index element={<ScenePage />} />
      <Route element={<AppShell />}>
        {/* Ancien accueil conservé comme filet de sécurité. */}
        <Route path="classique" element={<Accueil />} />
        <Route path="destinations" element={<Destinations />} />
        <Route path="trajets/:siteId" element={<Trajets />} />
        <Route path="comparer" element={<Comparer />} />
        <Route path="pre-reservation" element={<PreReservation />} />
        <Route path="dossier/:reference" element={<Dossier />} />
        <Route path="retour/:reference" element={<Retour />} />
        <Route path="*" element={<PageIntrouvable />} />
      </Route>
      {/* Vote en classe : hors du shell (écran projeté pour l'enseignant, page mobile pour les élèves). */}
      <Route path="vote/:code" element={<VoteEleve />} />
      <Route path="vote/:code/animer" element={<VoteAnimer />} />
    </Routes>
  )
}
