import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, isGroupRoute, type CatalogPlace, type ChatAction, type Edge, type ErrorCode, type Place, type Route } from "./api";
import { useI18n } from "./i18n";
import Header from "./components/Header";
import MapView from "./components/MapView";
import RoutePanel, { type TripDir } from "./components/RoutePanel";
import PrebookSheet from "./components/PrebookSheet";
import PlacesPanel from "./components/PlacesPanel";
import ChatPanel, { type ChatMessage } from "./components/ChatPanel";
import SimPanel from "./components/SimPanel";
import SchoolForm from "./components/SchoolForm";
import { DiscoverySheet } from "./components/Discovery";
import { DISCOVERIES, type Discovery } from "./data/discoveries";
import { TrainSim } from "./sim";
import { scheduleOf, type Booking, type Proposal } from "./school";
import type { Recommendations } from "./recommendations";
import RecoPanel from "./components/RecoPanel";
import { OFFER_END, OFFER_START, departuresOf, fromClock, pickDeparture, toClock } from "./reliability";
import { BottomNav, SheetGrip, sheetContentHeight, sheetHeights, useSheetDrag, useTopRoom, useViewport, type NavKey, type Snap } from "./components/MobileNav";

type Tab = "route" | "places";
const TAB_LABEL = { route: "tabRoute", places: "tabPlaces" } as const;

const normName = (s: string) => s.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export default function App() {
  const { t, locale } = useI18n();
  const [places, setPlaces] = useState<Place[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loadError, setLoadError] = useState<ErrorCode | null>(null);
  const [tab, setTab] = useState<Tab>("route");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [route, setRoute] = useState<Route | null>(null);
  const [routeError, setRouteError] = useState<ErrorCode | null>(null);
  const [loading, setLoading] = useState(false);
  // Heure de départ voulue (« HH:MM ») : celle du projet scolaire quand on vient d'une idée de sortie, sinon maintenant
  // Heure courante, ramenée dans la plage de l'offre (8 h - 16 h)
  const [departAfter, setDepartAfter] = useState(() => toClock(Math.min(OFFER_END, Math.max(OFFER_START, new Date().getHours() * 60 + new Date().getMinutes()))));
  // Idée de sortie ouverte : on bascule entre son aller et son retour, chacun avec son heure, puis on pré-réserve
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [dir, setDir] = useState<TripDir>("out");
  const [backAfter, setBackAfter] = useState("16:00");
  // Retour ajouté à un trajet simple (« Vous revenez aussi ? ») : même bascule aller / retour qu'une idée de sortie
  const [ret, setRet] = useState<{ outbound: Route; inbound: Route } | null>(null);
  const [addingReturn, setAddingReturn] = useState(false);
  const pair = proposal ?? ret;
  // Ce qui a été cherché (une ville garde son temps d'accès à la gare) : le retour cherche l'inverse exact
  const searched = useRef({ from: "", to: "" });
  const [prebook, setPrebook] = useState(false);
  // Lieu choisi depuis sa fiche (« Y aller en train ») : il nomme la sortie dans la pré-réservation, comme une idée
  const [visit, setVisit] = useState<Discovery | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [discovery, setDiscovery] = useState<Discovery | null>(null);
  const closeDiscovery = useCallback(() => setDiscovery(null), []);
  const closePrebook = useCallback(() => setPrebook(false), []);
  const [sim, setSim] = useState<TrainSim | null>(null);

  // Une simulation ne survit pas à un changement d'itinéraire (son horloge s'arrête quand plus rien ne l'affiche)
  useEffect(() => setSim(null), [route]);

  useEffect(() => {
    Promise.all([api.places(), api.network()])
      .then(([p, e]) => {
        setPlaces(p);
        setEdges(e);
      })
      .catch((e) => setLoadError(e instanceof ApiError ? e.code : "network"));
  }, []);

  // Lien direct vers un trajet : /?from=Toulouse&to=Carcassonne (&at=09:30 pour l'heure de départ)
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const f = q.get("from")?.trim();
    const d = q.get("to")?.trim();
    if (!f || !d) return;
    const at = q.get("at");
    setFrom(f);
    setTo(d);
    search(f, d, at && /^\d{1,2}:\d{2}$/.test(at) ? at : undefined);
  }, []);

  const byId = useMemo(() => new Map(places.map((p) => [p.id, p])), [places]);
  // Gare de départ / d'arrivée déjà choisie (nom exact, sans casse ni accents) : la carte la colore avant même
  // qu'un itinéraire existe, pour que l'on voie d'un coup d'œil d'où l'on part et où l'on va
  const byName = useMemo(() => new Map(places.map((p) => [normName(p.name), p.id])), [places]);
  const fromId = byName.get(normName(from)) ?? null;
  const toId = byName.get(normName(to)) ?? null;

  async function search(f = from, d = to, at?: string) {
    if (!f.trim() || !d.trim()) return;
    setLoading(true);
    setRouteError(null);
    try {
      setRoute(await api.trip(f.trim(), d.trim()));
      searched.current = { from: f.trim(), to: d.trim() };
      setProposal(null);
      setRet(null);
      setDir("out");
      setDepartAfter(at ?? toClock(new Date().getHours() * 60 + new Date().getMinutes()));
      // Le trajet trouvé s'écrit dans l'adresse : la copier suffit pour le partager (?from=…&to=…)
      const q = new URLSearchParams({ from: f.trim(), to: d.trim() });
      if (at) q.set("at", at);
      history.replaceState(null, "", `${location.pathname}?${q}`);
      setSelected(null);
    } catch (e) {
      setRoute(null);
      setRouteError(e instanceof ApiError ? e.code : "network");
    } finally {
      setLoading(false);
    }
  }

  // Depuis la carte ou la liste des lieux : remplir départ / arrivée, et chercher dès que les deux sont là.
  // Fonction stable (lit départ / arrivée dans une ref) : la carte, mémoïsée, ne se redessine pas à chaque frappe.
  const typed = useRef({ from, to });
  typed.current = { from, to };
  const pick = useCallback((which: "from" | "to", name: string, place?: Discovery) => {
    if (which === "to") setVisit(place ?? null);
    const f = which === "from" ? name : typed.current.from;
    const d = which === "to" ? name : typed.current.to;
    setFrom(f);
    setTo(d);
    setTab("route");
    setChatOpen(false);
    setSnap((s) => (s === "peek" ? "half" : s));
    // Sans l'autre extrémité, pas de recherche : on désélectionne quand même, la carte recule autour de la gare
    if (f && d) search(f, d);
    else setSelected(null);
  }, []);

  // Une idée de sortie choisie dans le projet scolaire : on affiche son aller comme un itinéraire classique
  const choose = useCallback((p: Proposal) => {
    setFrom(p.outbound.from);
    setTo(p.outbound.to);
    setRouteError(null);
    setRoute(p.outbound);
    const { out, back } = scheduleOf(p);
    setProposal(p);
    setRet(null);
    setDir("out");
    setDepartAfter(toClock(out.minute));
    if (back) setBackAfter(toClock(back.minute));
    setSelected(null);
  }, []);
  const switchDir = (d: TripDir) => {
    if (!pair) return;
    const r = d === "out" || !pair.inbound ? pair.outbound : pair.inbound;
    const q = searched.current;
    setDir(d);
    setFrom(proposal ? r.from : d === "out" ? q.from : q.to);
    setTo(proposal ? r.to : d === "out" ? q.to : q.from);
    setRoute(r);
  };
  // Le retour d'un trajet simple : l'itinéraire inverse, avec une heure par défaut trois heures après l'arrivée de l'aller
  async function addReturn() {
    const q = searched.current;
    if (proposal) return addProposalReturn(proposal);
    if (!route || !q.from) return;
    setAddingReturn(true);
    setRouteError(null);
    try {
      const inbound = await api.trip(q.to, q.from);
      const out = pickDeparture(departuresOf(route), fromClock(departAfter));
      setRet({ outbound: route, inbound });
      setBackAfter(toClock(Math.min(out.arrival + 180, 20 * 60)));
      setDir("back");
      setFrom(q.to);
      setTo(q.from);
      setRoute(inbound);
    } catch (e) {
      setRouteError(e instanceof ApiError ? e.code : "network");
    } finally {
      setAddingReturn(false);
    }
  }
  // Idée de sortie : le retour s'ajoute ou se retire ici aussi, quel que soit le choix fait dans le formulaire.
  // Un retour retiré est gardé de côté : le remettre ne relance pas de recherche.
  const stashedInbound = useRef<{ proposal: Proposal; inbound: Route } | null>(null);
  async function addProposalReturn(p: Proposal) {
    setAddingReturn(true);
    setRouteError(null);
    try {
      const stash = stashedInbound.current;
      const inbound =
        stash && stash.proposal.outbound === p.outbound
          ? stash.inbound
          : await api.schoolRoute(byId.get(p.discovery.stationId)?.name ?? p.outbound.to, p.project.origin);
      const next = { ...p, inbound };
      const { back } = scheduleOf(next);
      setProposal(next);
      if (back) setBackAfter(toClock(back.minute));
      setDir("back");
      setFrom(inbound.from);
      setTo(inbound.to);
      setRoute(inbound);
    } catch (e) {
      setRouteError(e instanceof ApiError ? e.code : "network");
    } finally {
      setAddingReturn(false);
    }
  }
  const removeReturn = () => {
    if (proposal) {
      if (!proposal.inbound) return;
      const next = { ...proposal, inbound: null };
      stashedInbound.current = { proposal: next, inbound: proposal.inbound };
      setProposal(next);
      setDir("out");
      setFrom(proposal.outbound.from);
      setTo(proposal.outbound.to);
      setRoute(proposal.outbound);
      return;
    }
    if (!ret) return;
    setRet(null);
    setDir("out");
    setFrom(searched.current.from);
    setTo(searched.current.to);
    setRoute(ret.outbound);
  };
  const backToProject = () => {
    setProposal(null);
    setRet(null);
    setRoute(null);
    setRouteError(null);
    setVisit(null);
    history.replaceState(null, "", location.pathname);
  };
  // Ce qu'on pré-réserve, quel que soit le chemin : l'idée de sortie avec son projet, ou le trajet trouvé sur la carte
  // (aller seul ou aller-retour) sans projet — le formulaire demandera alors le groupe. Seulement si tout est en TER.
  const booking = useMemo<Booking | null>(() => {
    const b: Booking | null = proposal
      ? { outbound: proposal.outbound, inbound: proposal.inbound, visit: proposal.discovery, project: proposal.project }
      : ret
        ? { outbound: ret.outbound, inbound: ret.inbound, visit, project: null }
        : route && { outbound: route, inbound: null, visit, project: null };
    return b && isGroupRoute(b.outbound) && (!b.inbound || isGroupRoute(b.inbound)) ? b : null;
  }, [proposal, ret, route, visit]);
  // Recommandations (projet scolaire aujourd'hui, assistant IA demain) : bandeau du bas + lieux en avant sur la carte
  const [recos, setRecos] = useState<Recommendations | null>(null);
  const recommendSchool = useCallback((found: Proposal[] | null) => {
    setRecos(found && { source: "school", items: found.map((p) => ({ discovery: p.discovery, proposal: p })) });
  }, []);
  const highlight = useMemo(() => new Set(recos?.items.map((r) => r.discovery.id)), [recos]);

  // ── Mobile : carte plein écran, panneau coulissant (la barre latérale), barre de navigation en bas ──
  const { mobile, h: viewportH } = useViewport();
  const [chatOpen, setChatOpen] = useState(false);
  const [snap, setSnap] = useState<Snap>("half");
  const sheet = useRef<HTMLElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const [navH, setNavH] = useState(64);
  useEffect(() => {
    const el = navRef.current;
    if (!mobile || !el) return;
    const ro = new ResizeObserver(() => setNavH(el.offsetHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, [mobile]);
  const top = useTopRoom(sheet, tab, mobile);
  // Hauteur du contenu, remesurée après chaque rendu (trajet trouvé, onglet, retour ajouté…) ; la conversation avec
  // l'assistant, elle, garde tout l'écran
  const [contentH, setContentH] = useState(Infinity);
  useLayoutEffect(() => {
    const el = sheet.current;
    const h = mobile && el && !chatOpen ? sheetContentHeight(el) : Infinity;
    if (Math.abs(h - contentH) > 1 || (h === Infinity) !== (contentH === Infinity)) setContentH(h);
  });
  const heights = useMemo(() => sheetHeights(viewportH, navH, top, contentH), [viewportH, navH, top, contentH]);
  const sheetH = mobile ? heights[snap] : 0;
  useSheetDrag({ sheet, heights, snap, onSnap: setSnap }, mobile);
  // Hauteur publiée en CSS : les bandeaux de simulation / recommandations et l'attribution de la carte se posent dessus
  useEffect(() => {
    const html = document.documentElement.style;
    html.setProperty("--sheet-h", `${sheetH}px`);
    html.setProperty("--nav-h", mobile ? `${navH}px` : "0px");
  }, [sheetH, navH, mobile]);
  // Le panneau suit ce qui se passe : un trajet trouvé s'ouvre à moitié, une simulation ou des idées de sortie
  // le replient pour laisser la carte et leur bandeau à l'écran
  useEffect(() => {
    if (route || routeError) setSnap("half");
  }, [route, routeError]);
  // …sauf pendant une discussion avec l'assistant : ses idées s'affichent sans replier la conversation
  useEffect(() => {
    if ((sim || recos) && !chatOpen) setSnap("peek");
  }, [sim, recos]);
  // Ce que la carte doit éviter : la recherche flottante en haut, panneau + navigation en bas (MapView ajoute
  // lui-même la hauteur réelle du bandeau de simulation / d'idées)
  const mapInset = useMemo(
    () => (mobile ? { top, bottom: navH + sheetH } : undefined),
    [mobile, top, navH, sheetH],
  );
  // ── Assistant : il connaît les lieux du site (avec leur gare) et pilote l'itinéraire et les recommandations ──
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const catalog = useMemo<CatalogPlace[]>(
    () =>
      DISCOVERIES.map((d) => ({
        id: d.id,
        title: d.title[locale],
        category: d.category,
        station: byId.get(d.stationId)?.name ?? "",
        summary: d.summary[locale],
      })),
    [byId, locale],
  );
  const onChatActions = useCallback(
    (actions: ChatAction[]) => {
      for (const a of actions) {
        if (a.type === "route") {
          setFrom(a.from);
          setTo(a.to);
          setVisit(null);
          setTab("route");
          search(a.from, a.to);
        } else {
          const items = a.items.flatMap(({ id, reason }) => {
            const discovery = DISCOVERIES.find((d) => d.id === id);
            return discovery ? [{ discovery, reason }] : [];
          });
          if (items.length) setRecos({ source: "ai", items });
        }
      }
    },
    // search lit départ / arrivée en argument : pas besoin de la recréer à chaque frappe
    [],
  );
  const chatProps = { open: chatOpen, setOpen: setChatOpen, catalog, onActions: onChatActions, messages: chatMessages, setMessages: setChatMessages };
  const navActive: NavKey = chatOpen ? "chat" : tab;
  const navigate = (k: NavKey) => {
    // L'assistant occupe le panneau du bas, comme les deux autres onglets
    if (k === "chat") {
      if (chatOpen) return setSnap((s) => (s === "peek" ? "half" : "peek"));
      setChatOpen(true);
      if (snap === "peek") setSnap("half");
      return;
    }
    setChatOpen(false);
    // Toucher l'onglet déjà ouvert replie ou rouvre le panneau, comme dans Google Maps
    if (k === tab && !chatOpen) return setSnap((s) => (s === "peek" ? "half" : "peek"));
    setTab(k);
    if (snap === "peek") setSnap("half");
  };

  return (
    <div className="app">
      {!mobile && <Header />}
      <main className="layout">
        <aside
          ref={sheet}
          className={mobile ? `sidebar sheet-${snap}${chatOpen ? " is-chat" : ""}` : "sidebar"}
          style={mobile ? { height: heights[snap] } : undefined}
          // Un champ du panneau touché (projet scolaire) : on l'ouvre en grand, le clavier va prendre le bas de l'écran.
          // Pas pour la recherche du haut : sur mobile elle flotte sur la carte, hors du panneau
          onFocus={(e) => {
            if (mobile && snap !== "full" && e.target.matches(":is(.panel-body, .chat-input) :is(input, textarea, select)")) setSnap("full");
          }}
        >
          {mobile && <SheetGrip sheet={sheet} heights={heights} snap={snap} onSnap={setSnap} />}
          {mobile && <ChatPanel docked {...chatProps} />}
          <div className="tabs" role="tablist">
            {(["route", "places"] as Tab[]).map((k) => (
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "tab active" : "tab"} onClick={() => setTab(k)}>
                {t[TAB_LABEL[k]]}
              </button>
            ))}
          </div>
          {loadError && <p className="alert">{t.errors[loadError]}</p>}
          {tab === "route" ? (
            <RoutePanel
              places={places}
              from={from}
              to={to}
              setFrom={setFrom}
              setTo={setTo}
              onSearch={() => {
                // Champ d'arrivée retapé : le lieu choisi sur sa fiche ne correspond plus
                if (visit && byId.get(visit.stationId)?.name !== to.trim()) setVisit(null);
                search();
              }}
              loading={loading}
              route={route}
              error={routeError}
              departAfter={pair && dir === "back" ? backAfter : departAfter}
              setDepartAfter={pair && dir === "back" ? setBackAfter : setDepartAfter}
              trip={
                pair && {
                  outbound: pair.outbound,
                  inbound: pair.inbound,
                  dir,
                  outAfter: departAfter,
                  backAfter,
                  onDir: switchDir,
                  onRemove: removeReturn,
                }
              }
              onAddReturn={addReturn}
              addingReturn={addingReturn}
              onPrebook={booking ? () => setPrebook(true) : undefined}
              fromProject={!!proposal}
              sim={sim}
              onSimulate={() => route && setSim(new TrainSim(route, byId))}
              onBack={backToProject}
            >
              <SchoolForm places={places} byId={byId} onResults={recommendSchool} />
            </RoutePanel>
          ) : (
            <PlacesPanel places={places} byId={byId} selected={selected} onSelect={setSelected} onPick={pick} onOpenDiscovery={setDiscovery} />
          )}
          <p className="data-note">{t.dataNote}</p>
        </aside>
        <MapView places={places} edges={edges} byId={byId} route={route} fromId={fromId} toId={toId} sim={sim} inset={mapInset} highlight={highlight} selected={selected} onSelect={setSelected} onPick={pick} onOpenDiscovery={setDiscovery} />
        {/* Bandeaux du bas : sous la carte seulement, la barre latérale garde toute la hauteur */}
        {sim ? (
          <SimPanel sim={sim} byId={byId} onStop={() => setSim(null)} onOpenDiscovery={setDiscovery} />
        ) : (
          recos && <RecoPanel recos={recos} byId={byId} onChoose={choose} onOpenDiscovery={setDiscovery} onClose={() => setRecos(null)} />
        )}
      </main>
      {!mobile && <ChatPanel {...chatProps} />}
      {mobile && <BottomNav active={navActive} onChange={navigate} navRef={navRef} />}
      {prebook && booking && <PrebookSheet booking={booking} outAfter={departAfter} backAfter={backAfter} onClose={closePrebook} />}
      {discovery && <DiscoverySheet d={discovery} station={byId.get(discovery.stationId)} onClose={closeDiscovery} onPick={pick} />}
    </div>
  );
}
