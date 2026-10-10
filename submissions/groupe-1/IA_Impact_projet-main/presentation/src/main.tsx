// Diapo « L'Occitanie en train » (projet IA Impact).
import { createRoot } from "react-dom/client";
import { Deck } from "./components/Deck";
import { SLIDES } from "./slides";
import "./styles/fonts.css";
import "./styles/deck.css";

// Pas de StrictMode : il monterait le moteur deux fois en développement, et les animations avec
createRoot(document.getElementById("root")!).render(<Deck slides={SLIDES} />);
