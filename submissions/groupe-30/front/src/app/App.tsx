import { useEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router";
import {
  Building2,
  ClipboardList,
  Database,
  LayoutList,
  Menu,
  ShieldCheck,
  X,
  ArrowUpRight,
  MapPin,
  Coins,
} from "lucide-react";
import { DataProvider, useAppData } from "../data/store";
import { AuthGate } from "../data/AuthGate";
import { EquipmentList } from "../features/review/EquipmentList";
import { EquipmentDetail } from "../features/equipment/EquipmentDetail";
import { ActionsPage } from "../features/actions/ActionsPage";
import { ToulouseMap } from "../features/map/ToulouseMap";
import { DataDialog } from "../features/review/DataDialog";
import { EconomicsPage } from "../features/economics/EconomicsPage";

function Shell() {
  const [dataOpen, setDataOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { actions, lastListQuery, logout, notify } = useAppData();
  const location = useLocation();
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width:900px)").matches,
  );
  const navigation = useRef<HTMLElement>(null);
  const previousMenuOpen = useRef(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width:900px)");
    const update = () => {
      setNarrow(media.matches);
      setMenuOpen(false);
    };
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (menuOpen)
      navigation.current?.querySelector<HTMLAnchorElement>("nav a")?.focus();
    else if (previousMenuOpen.current && narrow)
      document
        .querySelector<HTMLButtonElement>('[aria-label="Ouvrir la navigation"]')
        ?.focus();
    previousMenuOpen.current = menuOpen;
  }, [menuOpen, narrow]);
  const activeActions = actions.filter((a) => a.status !== "closed").length;
  const title =
    location.pathname === "/actions"
      ? "Actions"
      : location.pathname === "/economies"
        ? "Arbitrages budgétaires"
        : location.pathname === "/carte"
          ? "Carte du patrimoine"
          : location.pathname === "/equipements"
            ? "Équipements"
            : location.pathname.startsWith("/equipements/")
              ? "Fiche équipement"
              : "À examiner";
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Aller au contenu
      </a>
      {menuOpen && (
        <button
          className="menu-backdrop"
          aria-label="Fermer la navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside
        id="main-navigation"
        ref={navigation}
        inert={narrow && !menuOpen}
        onKeyDown={(event) => {
          if (!narrow || !menuOpen) return;
          if (event.key === "Escape") {
            setMenuOpen(false);
          }
          if (event.key === "Tab") {
            const controls = Array.from(
              navigation.current!.querySelectorAll<HTMLElement>(
                "a[href],button",
              ),
            ).filter((el) => el.offsetParent !== null);
            const first = controls[0],
              last = controls.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
        className={`sidebar ${menuOpen ? "open" : ""}`}
      >
        <div className="brand">
          <img src="/brand/action-logement-logo.png" alt="Action Logement" />
          <button
            className="icon-button mobile-only"
            aria-label="Fermer la navigation"
            onClick={() => setMenuOpen(false)}
          >
            <X size={19} />
          </button>
        </div>
        <Link to="/examiner" className="product-brand">
          <span className="product-mark">
            <ShieldCheck size={21} />
          </span>
          <span>
            <strong>BâtIA</strong>
            <small>Prévention des pannes</small>
          </span>
        </Link>
        <span className="nav-label">VOTRE ESPACE</span>
        <nav aria-label="Navigation principale">
          <NavLink
            to={"/examiner" + lastListQuery}
            onClick={() => setMenuOpen(false)}
          >
            <LayoutList size={19} />À examiner
          </NavLink>
          <NavLink to="/actions" onClick={() => setMenuOpen(false)}>
            <ClipboardList size={19} />
            Actions
            {activeActions > 0 && (
              <span className="nav-count">{activeActions}</span>
            )}
          </NavLink>
          <NavLink to="/economies" onClick={() => setMenuOpen(false)}>
            <Coins size={19} />
            Arbitrages budgétaires
          </NavLink>
          <NavLink to="/equipements" end onClick={() => setMenuOpen(false)}>
            <Building2 size={19} />
            Équipements
          </NavLink>
          <NavLink to="/carte" onClick={() => setMenuOpen(false)}>
            <MapPin size={19} />
            Carte Toulouse
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <button
            className="sidebar-data"
            onClick={() => {
              setDataOpen(true);
              setMenuOpen(false);
            }}
          >
            <Database size={16} />
            Données et classement
            <ArrowUpRight size={14} />
          </button>
          <div className="team-profile">
            <span>AL</span>
            <div>
              <strong>Équipe technique</strong>
              <small>Gestion du patrimoine</small>
            </div>
          </div>
          <button
            className="sidebar-data"
            onClick={() => void logout().catch((e) => notify(e.message))}
          >
            Se déconnecter
          </button>
        </div>
      </aside>
      <div className="workspace" inert={narrow && menuOpen}>
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-only"
              aria-label="Ouvrir la navigation"
              aria-controls="main-navigation"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb">
              Prévention<span>/</span>
              <strong>{title}</strong>
            </span>
          </div>
          <div className="topbar-actions">
            <span className="workspace-label">
              <span />
              Espace technique
            </span>
            <button className="button subtle" onClick={() => setDataOpen(true)}>
              <Database size={16} />
              Données
            </button>
            <span className="avatar" aria-label="Équipe Action Logement">
              AL
            </span>
          </div>
        </header>
        <main id="main-content" className="main-content">
          <Routes>
            <Route path="/examiner" element={<EquipmentList />} />
            <Route path="/equipements" element={<EquipmentList inventory />} />
            <Route path="/equipements/:id" element={<EquipmentDetail />} />
            <Route path="/carte" element={<ToulouseMap />} />
            <Route path="/actions" element={<ActionsPage />} />
            <Route path="/economies" element={<EconomicsPage />} />
            <Route path="*" element={<Navigate to="/examiner" replace />} />
          </Routes>
        </main>
        <footer className="app-footer">
          <span>BâtIA · Prévention</span>
          <span>Au service de votre patrimoine.</span>
        </footer>
      </div>
      {dataOpen && <DataDialog onClose={() => setDataOpen(false)} />}
    </div>
  );
}
export default function App() {
  return (
    <BrowserRouter>
      <AuthGate>
        <DataProvider>
          <Shell />
        </DataProvider>
      </AuthGate>
    </BrowserRouter>
  );
}
