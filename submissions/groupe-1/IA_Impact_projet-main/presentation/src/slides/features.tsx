// Ce que fait le site, une fonctionnalité par slide, chacune avec sa petite démo animée.
import { Fragment } from "react";
import { Icon, Trame, Words } from "../components/primitives";
import { Net } from "../components/Net";
import { IDEAS, MODEL, PHOTOS, ROUTE, SCENERY, ST, VIDEOS } from "../data";
import type { SlideDef } from "../engine/deck";
import { press, STEP, typeInto } from "../engine/enter";
import { enterNet, routeOn } from "../engine/net";
import { loadIntro3D, loadModelViewer } from "../engine/three";
import { $, $$, A, BACK, EASE, FLAGS, RED, YELLOW, easeIO, fmtMin, html, short, typo } from "../engine/util";
import { T } from "../textes";

export const solution: SlideDef = {
  id: "solution", tone: "dark", cls: "s-solution", trans: "push",
  Body: () => {
    const cards = [
      ["route", T.card1Title, T.card1], ["pin", T.card2Title, T.card2], ["train", T.card3Title, T.card3], ["photo", T.card4Title, T.card4],
    ] as const;
    return (
      <>
        <div className="kicker" data-in="flap">{T.solutionKick}</div>
        <Words className="title" data-d={1} text={T.solutionTitle} />
        <div className="cards">
          {cards.map(([ico, title, text], i) => (
            <article key={ico} className="card" data-in="pop" data-d={5 + i}>
              <div className="card-in" data-idle="float">
                <Icon name={ico} className="ico" />
                <h3 dangerouslySetInnerHTML={html(title)} /><p dangerouslySetInnerHTML={html(text)} />
              </div>
            </article>
          ))}
        </div>
      </>
    );
  },
};

/** Tronçons du trajet, avec la correspondance entre les deux */
function Legs({ full, base }: { full: boolean; base?: number }) {
  return (
    <>
      {ROUTE.legs.map((l, i) => {
        const inn = (k: number) => (base != null ? { "data-in": "left", "data-d": base + i * 2 + k } : {});
        return (
          <Fragment key={i}>
            {l.wait > 0 && <div className="leg-wait" {...inn(0)} dangerouslySetInnerHTML={html(T.routeChangeAt(short(l.from), fmtMin(l.wait)))} />}
            <div className="leg-card" {...inn(1)}>
              <span className="bar" style={{ background: i ? YELLOW : RED }} />
              <div>
                <h4>{full ? `${l.from} → ${l.to}` : `${short(l.from)} → ${short(l.to)}`}</h4>
                <p>{`TER liO · ${full ? `${l.line} · ` : ""}${T.routeStops(l.stops.length - 2)} · ${T.routePerDay(l.perDay)}`}</p>
              </div>
              <span className="dur">{fmtMin(l.minutes)}</span>
            </div>
          </Fragment>
        );
      })}
    </>
  );
}

// Démo de recherche : on tape le départ, l'arrivée, on clique, le résultat se déplie et le trajet se dessine
export const search: SlideDef = {
  id: "search", tone: "light", cls: "s-search", trans: "ter3d-front",
  Body: () => (
    <>
      <Net kind="route" />
      <div className="col">
        <div className="kicker" data-in="flap">{T.k3}</div>
        <Words className="title" data-d={1} text={T.searchTitle} />
        <div className="mock-search" data-in="up" data-d={4}>
          <div className="ms-hero">
            <div className="ms-q" dangerouslySetInnerHTML={html(T.msQuestion)} />
            <div className="ms-field"><i className="yellow" /><span data-type-from="" /><b className="caret" /></div>
            <div className="ms-field"><i className="red" /><span data-type-to="" /><b className="caret" /></div>
            <div className="ms-btn">{T.msButton}</div>
          </div>
          <div className="ms-result">
            <div className="ms-total"><small>{T.routeTotal}</small><b>{fmtMin(ROUTE.minutes)}</b><span className="pill-tag">{T.routeChanges(ROUTE.legs.length - 1)}</span></div>
            <Legs full={false} />
          </div>
        </div>
      </div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    const from = $(el, "[data-type-from]"), to = $(el, "[data-type-to]");
    const carets = $$(el, ".caret"), btn = $(el, ".ms-btn"), result = $(el, ".ms-result");
    from.textContent = ""; to.textContent = "";
    const svg = $<SVGSVGElement>(el, ".net-route:not(.net-ov)");
    enterNet(run, svg, t0, { draw: 1400 });
    const t1 = t0 + 4 * STEP + 900;
    carets.forEach((c, i) => A(c, [{ opacity: 0 }, { opacity: 1 }], { duration: 10, delay: i ? 0 : t1 }));
    const e1 = typeInto(run, from, ROUTE.from, t1);
    run.later(e1 + 150, () => { carets[0].style.visibility = "hidden"; carets[1].getAnimations().forEach((a) => a.cancel()); carets[1].style.opacity = "1"; });
    const e2 = typeInto(run, to, short(ROUTE.to), e1 + 250);
    run.later(e2 + 100, () => (carets[1].style.visibility = "hidden"));
    press(btn, e2 + 350);
    A(result, [{ opacity: 0, transform: "translateY(30px)", maxHeight: "0px" }, { opacity: 1, transform: "none", maxHeight: "700px" }], { duration: 900, delay: e2 + 650 });
    $$(result, ".ms-total, .leg-wait, .leg-card").forEach((c, i) => A(c, [{ opacity: 0, transform: "translateX(-60px)" }, { opacity: 1, transform: "none" }], { duration: 700, delay: e2 + 800 + i * 140 }));
    routeOn(run, svg, e2 + 700);
    run.later(0, () => carets.forEach((c) => (c.style.visibility = "")));
  },
};

// Exemple réel : titre, durée et tronçons de l'itinéraire calculé par le backend
export const route: SlideDef = {
  id: "route", tone: "dark", cls: "s-route", trans: "iris",
  Body: () => (
    <>
      <Net kind="route" />
      <div className="col">
        <div className="kicker" data-in="flap">{T.routeKick}</div>
        <Words className="title" data-d={1} text={`${short(ROUTE.from)} → <em>${short(ROUTE.to)}</em>`} />
        <div className="route-total" data-in="up" data-d={4}><b>{fmtMin(ROUTE.minutes)}</b><span className="pill-tag">{T.routeChanges(ROUTE.legs.length - 1)}</span></div>
        <div className="legs"><Legs full base={6} /></div>
        <p className="foot" data-in="up" data-d={12} dangerouslySetInnerHTML={html(T.routeFoot)} />
      </div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    const svg = $<SVGSVGElement>(el, ".net-route:not(.net-ov)");
    enterNet(run, svg, t0, { draw: 1400 });
    routeOn(run, svg, t0 + 900);
  },
};

// Simulation : le train parcourt le trajet, le panneau donne l'heure, l'avancement et l'endroit
const NEAR = { "chateau-collioure": "Château royal de Collioure", "cite-carcassonne": "La Cité de Carcassonne", "canal-du-midi": "Canal du Midi", "viaduc-millau": "Viaduc de Millau" } as const;
export const sim: SlideDef = {
  id: "sim", tone: "dark", cls: "s-sim", trans: "ter3d",
  Body: () => (
    <>
      <Net kind="sim" />
      <div className="col">
        <div className="kicker" data-in="flap">{T.k4}</div>
        <Words className="title" data-d={1} text={T.simTitle} />
        <p className="lead" data-in="up" data-d={4} dangerouslySetInnerHTML={html(T.simLead)} />
      </div>
      <div className="sim-card" data-in="up" data-d={6}>
        <div className="sim-top"><i className="live" /><b>{T.simCard}</b><span className="sim-clock" data-sim-clock="">08:00</span></div>
        <div className="sim-bar"><i data-sim-fill="" /></div>
        <div className="sim-row"><span className="sim-play">❚❚</span><p data-sim-status="" /><span className="sim-speed"><b>×1</b><span>×2</span><span>×4</span></span></div>
        <div className="sim-near" data-sim-near="" />
      </div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    const svg = $<SVGSVGElement>(el, ".net-sim:not(.net-ov)");
    enterNet(run, svg, t0, { draw: 1200 });
    const clock = $(el, "[data-sim-clock]"), fill = $(el, "[data-sim-fill]");
    const status = $(el, "[data-sim-status]"), near = $(el, "[data-sim-near]");
    let lastNear = "";
    routeOn(run, svg, t0 + 600, ({ leg, f, phase, i, s }) => {
      const l = ROUTE.legs[leg];
      const before = ROUTE.legs.slice(0, leg).reduce((a, x) => a + x.wait + x.minutes, 0) + (leg ? l.wait : 0);
      const m = phase === "wait" && leg === 0 ? ROUTE.legs[0].minutes : before + f * l.minutes;
      const hh = 8 * 60 + Math.round(m);
      clock.textContent = `${String(Math.floor(hh / 60)).padStart(2, "0")}:${String(hh % 60).padStart(2, "0")}`;
      fill.style.width = `${Math.min(100, (m / ROUTE.minutes) * 100)}%`;
      const name = (k: number) => ST[l.stops[k]][2];
      status.textContent = phase === "wait" ? (leg === 0 ? T.simChange(short(l.to)) : T.simArrived(short(l.to)))
        : s < 0.08 ? T.simAt(name(i - 1)) : s > 0.92 ? T.simAt(name(i)) : T.simBetween(name(i - 1), name(i));
      // Lieu à voir le plus proche : la carte change quand on passe près d'un autre
      const here: keyof typeof NEAR = leg === 0 ? (f < 0.35 ? "chateau-collioure" : f < 0.75 ? "cite-carcassonne" : "canal-du-midi") : "viaduc-millau";
      if (here !== lastNear) {
        lastNear = here;
        near.innerHTML = `<small>${T.simNear}</small><div class="near-card"><img src="${PHOTOS[here].file}" alt=""/><b>${NEAR[here]}</b></div>`;
        near.animate([{ opacity: 0, transform: "translateX(40px)" }, { opacity: 1, transform: "none" }], { duration: 600, easing: EASE });
      }
    });
  },
};

// Hublot : le paysage défile, accélère, freine, s'arrête à quai, repart — sans fin
export const windowSlide: SlideDef = {
  id: "window", tone: "light", cls: "s-window", trans: "iris",
  Body: () => (
    <>
      <div className="col">
        <div className="kicker" data-in="flap">{T.k5}</div>
        <Words className="title" data-d={1} text={T.windowTitle} />
        <ul className="bullets">
          {(["red", "yellow", "navy"] as const).map((c, i) => (
            <li key={c} data-in="left" data-d={5 + i}><span className={`pill ${c}`} data-idle="pulse" /><div dangerouslySetInnerHTML={html([T.win1, T.win2, T.win3][i])} /></li>
          ))}
        </ul>
      </div>
      <div className="hublot" data-in="zoom" data-d={3}>
        <div className="hublot-view">
          <div className="strip">
            {SCENERY.map((s) => (
              <figure key={s.id} className="tile"><img src={s.file} alt="" draggable={false} /><figcaption>{s.place && <i>À voir</i>}{s.title}</figcaption></figure>
            ))}
          </div>
          <div className="poles"><i /><i /><i /></div>
          <div className="platform"><span>{T.winPlatform}</span></div>
          <div className="glass" />
        </div>
        <div className="hublot-tag"><i className="live" /><span>{T.winTag}</span></div>
      </div>
      <p className="credits">{`${T.sceneryCredits} ` + SCENERY.map((s) => `${s.title} : ${s.author} (${s.license})`).join(" · ")}</p>
    </>
  ),
  enter: ({ el, t0, run }) => {
    const tiles = $$(el, ".tile"), poles = $$(el, ".poles i"), platform = $(el, ".platform"), view = $(el, ".hublot-view");
    const TW = 640, n = tiles.length, V = 520, ACC = 1600, CRUISE = 5200, DEC = 1900, STOP = 2600;
    const cycle = ACC + CRUISE + DEC + STOP;
    const dist = (V * ACC) / 2000 + (V * CRUISE) / 1000 + (V * DEC) / 2000; // px parcourus par cycle
    const start = performance.now() + t0 + 400;
    run.tick((now) => {
      const t = Math.max(0, now - start), k = Math.floor(t / cycle), r = t % cycle;
      let d: number, v: number;
      if (r < ACC) { v = V * (r / ACC); d = (V * r * r) / (2 * ACC * 1000); }
      else if (r < ACC + CRUISE) { v = V; d = (V * ACC) / 2000 + (V * (r - ACC)) / 1000; }
      else if (r < ACC + CRUISE + DEC) { const q = r - ACC - CRUISE; v = V * (1 - q / DEC); d = (V * ACC) / 2000 + (V * CRUISE) / 1000 + (V * q - (V * q * q) / (2 * DEC)) / 1000; }
      else { v = 0; d = dist; }
      const off = k * dist + d;
      tiles.forEach((tile, i) => { const x = ((i * TW - off) % (n * TW) + n * TW) % (n * TW) - TW; tile.style.transform = `translateX(${x}px)`; });
      poles.forEach((p, j) => { const x = ((j * 900 - off * 2.6) % 2700 + 2700) % 2700 - 200; p.style.transform = `translateX(${x}px)`; });
      view.style.translate = `0 ${v > 0 ? Math.sin(now / 45) * 1.6 * (v / V) : 0}px`;
      platform.classList.toggle("in", r > ACC + CRUISE + DEC - 300 && t > 0);
    });
  },
};

// Sortie scolaire : les champs se remplissent, on clique, les idées arrivent comme des wagons qui freinent
export const school: SlideDef = {
  id: "school", tone: "light", cls: "s-school", trans: "flap",
  Body: () => (
    <>
      <div className="kicker" data-in="flap">{T.k7}</div>
      <Words className="title" data-d={1} text={T.schoolTitle} />
      <div className="school">
        <div className="form-card" data-in="up" data-d={4}>
          <h4>Préparer une sortie scolaire</h4>
          {T.form.map(([label, value]) => <label key={label}><small>{label}</small><span className="field" data-value={value} /></label>)}
          <div className="ms-btn red">{T.formButton}</div>
        </div>
        <div className="ideas">
          <div className="ideas-title">{T.ideasTitle}</div>
          {IDEAS.map((d) => (
            <div key={d.title} className="idea"><img src={d.file} alt="" draggable={false} />
              <div><b>{d.title}</b><span>{d.city}</span><em>{T.ideaTrain(fmtMin(d.minutes), d.transfers)}</em></div>
              <i className="wh l" /><i className="wh r" /></div>
          ))}
        </div>
      </div>
      <p className="credits">{`${T.photoCredits} ` + IDEAS.map((d) => `${d.title} : ${d.author} (${d.license})`).join(" · ")}</p>
    </>
  ),
  enter: ({ el, t0, run }) => {
    let at = t0 + 4 * STEP + 1000;
    $$(el, ".field").forEach((f) => { at = typeInto(run, f, f.dataset.value ?? "", at, 28) + 120; });
    press($(el, ".form-card .ms-btn"), at + 100);
    A($(el, ".ideas-title"), [{ opacity: 0, transform: "translateY(20px)" }, { opacity: 1, transform: "none" }], { duration: 600, delay: at + 400 });
    $$(el, ".idea").forEach((c, i) => {
      const d = at + 500 + i * 260;
      A(c, [{ opacity: 1, transform: "translateX(1300px)" }, { opacity: 1, transform: "none" }], { duration: 1500, delay: d, easing: "cubic-bezier(.15,.75,.25,1)" });
      c.querySelectorAll(".wh").forEach((w) => A(w, [{ rotate: "0deg" }, { rotate: "-1080deg" }], { duration: 1500, delay: d, easing: "cubic-bezier(.15,.75,.25,1)" }));
    });
  },
};

// Assistant : le message s'écrit, l'assistant « tape », puis répond
export const assistant: SlideDef = {
  id: "assistant", tone: "dark", cls: "s-assistant", trans: "cube",
  Body: () => (
    <>
      <div className="col">
        <div className="kicker" data-in="flap">{T.k8}</div>
        <Words className="title" data-d={1} text={T.assistantTitle} />
        <span className="soon" data-in="pop" data-d={6} data-idle="pulse">{T.soon}</span>
      </div>
      <div className="chat" data-in="right" data-d={3}>
        <div className="chat-head"><i className="live" /><b>{T.chatHead}</b></div>
        <div className="chat-body">
          <div className="msg bot">{typo("Bonjour ! Posez-moi vos questions sur un trajet, une gare ou un lieu à visiter.")}</div>
          <div className="msg user"><span data-chat-user="" /></div>
          <div className="msg bot typing"><i /><i /><i /></div>
          <div className="msg bot reply">{typo(T.chatBot)}<div className="chips"><span>Itinéraire</span><span>Lieux à voir</span><span>Sortie</span></div></div>
        </div>
        <div className="chat-input"><span>{T.chatPh}</span><i>➤</i></div>
      </div>
      <div className="chat-bubble" data-in="pop" data-d={8} data-idle="bob">💬</div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    const msgs = $$(el, ".msg"), user = $(el, "[data-chat-user]");
    const pop = (m: HTMLElement, d: number) => A(m, [{ opacity: 0, transform: "translateY(24px) scale(.96)" }, { opacity: 1, transform: "none" }], { duration: 500, delay: d, easing: BACK });
    const b = t0 + 3 * STEP + 900;
    pop(msgs[0], b);
    pop(msgs[1], b + 500);
    const e = typeInto(run, user, T.chatUser, b + 600, 30);
    pop(msgs[2], e + 300);
    A(msgs[2], [{ opacity: 1 }, { opacity: 0, maxHeight: "0px", padding: "0px", margin: "0px" }], { duration: 250, delay: e + 1700, fill: "forwards" });
    pop(msgs[3], e + 1800);
    msgs[2].querySelectorAll("i").forEach((d, i) => d.animate({ translate: ["0 0", "0 -8px"] }, { duration: 380, delay: i * 120, iterations: Infinity, direction: "alternate", easing: "ease-in-out" }));
  },
};

// 02 · Le site : les fonctionnalités en wagons, le train arrive, puis avance d'un wagon à la fois
export const overview: SlideDef = {
  id: "overview", tone: "dark", cls: "s-overview", trans: "train",
  Body: () => (
    <>
      <div className="kicker" data-in="flap">{T.k2}</div>
      <Words className="title" data-d={1} text={T.overviewTitle} />
      <div className="wagons">
        <div className="wagon-train">
          {T.wagons.map(([k, title], i) => (
            <div key={k} className="wagon" data-i={i}>
              <div className="wagon-box"><Icon name={k} className="ico" /><h3>{title}</h3></div>
              <i className="wh l" /><i className="wh r" /><i className="hitch" />
            </div>
          ))}
        </div>
        <div className="wagon-rails" />
      </div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    const wagons = $$(el, ".wagon"), wheels = $$(el, ".wh"), rails = $(el, ".wagon-rails");
    const SP = 470, n = wagons.length, CENTER = 960 - 210;
    const ARRIVE = 2200, MOVE = 1150, STOP = 1900;
    const start = performance.now() + t0;
    run.tick((now) => {
      const t = now - start;
      let pos: number; // distance parcourue par le train, en px
      if (t < ARRIVE) pos = -2600 * Math.pow(1 - Math.max(0, t / ARRIVE), 3);
      else {
        const c = t - ARRIVE, k = Math.floor(c / (MOVE + STOP)), r = c % (MOVE + STOP);
        pos = (k + easeIO(Math.min(1, r / MOVE))) * SP;
      }
      let hot: HTMLElement | null = null, best = Infinity;
      wagons.forEach((w, i) => {
        let x = i * SP - pos;
        if (t >= ARRIVE) x = ((x % (n * SP)) + n * SP) % (n * SP) - SP;
        w.style.transform = `translateX(${CENTER + x}px)`;
        if (Math.abs(x) < best) { best = Math.abs(x); hot = w; }
      });
      wagons.forEach((w) => w.classList.toggle("hot", w === hot && best < 30));
      wheels.forEach((wh) => (wh.style.rotate = `${pos / 0.22}deg`));
      rails.style.backgroundPositionX = `${-pos}px`;
    });
  },
};

// Vidéos du vrai site, pilotées par Claude : l'écran arrive, la caméra zoome en suivant les plans notés à l'enregistrement
function videoSlide(name: string, trans: SlideDef["trans"], kick: string, title: string): SlideDef {
  return {
    id: `video-${name}`, tone: "dark", cls: "s-video", trans,
    Body: () => (
      <>
        <Trame className="bg-trame" rows={7} cols={60} palette={["navy2", "navy2", "red"]} data-idle="drift" />
        <div className="screen" data-in="screen" data-idle="float">
          <div className="screen-bar"><i /><i /><i /><span>occitanie-en-train</span></div>
          <div className="screen-view"><video muted playsInline preload="auto" src={VIDEOS[name]?.file} /></div>
        </div>
        <div className="chip-title" data-in="mask" data-d={4}><span className="chip-kick">{kick}</span><span dangerouslySetInnerHTML={html(title)} /></div>
      </>
    ),
    enter: ({ el, t0, run }) => {
      const meta = VIDEOS[name], v = $<HTMLVideoElement>(el, "video"), view = $(el, ".screen-view");
      if (!meta) return;
      v.pause(); v.currentTime = 0;
      run.later(t0 + 1500, () => void v.play().catch(() => {}));
      const VW = 1600, VH = 900;
      let idx = -1, from = { z: 1, x: 0.5, y: 0.5 }, cur = { ...from };
      run.tick(() => {
        const t = v.currentTime, cams = meta.cams;
        let i = 0;
        while (i + 1 < cams.length && cams[i + 1].t <= t) i++;
        if (i !== idx) { idx = i; from = { ...cur }; }
        const c = cams[i], k = easeIO(Math.min(1, Math.max(0, (t - c.t) / c.e)));
        cur = { z: from.z + (c.z - from.z) * k, x: from.x + (c.x - from.x) * k, y: from.y + (c.y - from.y) * k };
        const tx = Math.min(0, Math.max(VW - VW * cur.z, VW / 2 - cur.x * VW * cur.z));
        const ty = Math.min(0, Math.max(VH - VH * cur.z, VH / 2 - cur.y * VH * cur.z));
        v.style.transform = `translate(${tx}px, ${ty}px) scale(${cur.z})`;
        // L'écran s'incline un peu vers ce que regarde la caméra : profondeur
        const zz = cur.z - 1;
        view.style.transform = `perspective(2200px) rotateY(${(cur.x - 0.5) * -9 * zz}deg) rotateX(${(cur.y - 0.5) * 7 * zz}deg)`;
      });
    },
    leave: (el) => el.querySelector("video")?.pause(),
  };
}
export const videoRoute = videoSlide("itineraire", "cube", "Itinéraire", "Votre trajet <em>en un clic</em>");
export const videoSim = videoSlide("simulation", "zoom", "Simulation · par la fenêtre", "Le trajet <em>en direct</em>");
export const videoPlaces = videoSlide("lieux", "push", "Lieux · monuments en 3D", "Des lieux <em>à découvrir</em>");
export const videoSchool = videoSlide("scolaire", "train", "Sortie scolaire", "Une sortie de classe <em>en train</em>");

// « Suivez le train » en 3D : le trajet se dessine, la caméra suit la rame, correspondance à Toulouse, arrivée à Albi
export const follow3d: SlideDef = {
  id: "follow", tone: "dark", cls: "s-3d", trans: "flap",
  Body: () => (
    <>
      <div className="stage3d" />
      <div className="chip-title" data-in="mask" data-d={4}><span className="chip-kick">En 3D</span>Suivez <em>le train</em></div>
      <div className="caption3d" />
    </>
  ),
  enter: ({ el, t0 }) => {
    const cap = $(el, ".caption3d");
    const caption = (c: string | null) => {
      cap.classList.remove("in");
      if (!c) return;
      cap.innerHTML = `<b>${c}</b>`;
      void cap.offsetWidth;
      cap.classList.add("in");
    };
    void loadIntro3D().then((m) => m.Deck3D.play(el, "follow", t0, caption));
  },
  leave: (el) => void loadIntro3D().then((m) => m.Deck3D.stop(el)),
};

// 06 · Lieux à découvrir : photos jetées sur la table, et un monument en 3D qui tourne (une photo avec ?lite)
const PHOTO_TITLES = { "cite-carcassonne": "Cité de Carcassonne", "pont-valentre": "Pont Valentré", "viaduc-millau": "Viaduc de Millau", "chateau-collioure": "Collioure" } as const;
const photoKeys = Object.keys(PHOTO_TITLES) as (keyof typeof PHOTO_TITLES)[];
const MODEL_VIEWER = `<model-viewer camera-controls disable-zoom auto-rotate auto-rotate-delay="0" rotation-per-second="18deg"
  interaction-prompt="none" shadow-intensity="0" exposure="1.05" camera-orbit="30deg 62deg 80%" alt="${MODEL.title}"></model-viewer>`;
export const discover: SlideDef = {
  id: "discover", tone: "dark", cls: "s-discover", trans: "ter3d-front",
  Body: () => (
    <>
      <div className="col">
        <div className="kicker" data-in="flap">{T.k6}</div>
        <Words className="title" data-d={1} text={T.discoverTitle} />
        <p className="lead" data-in="up" data-d={4} dangerouslySetInnerHTML={html(T.discoverLead)} />
        <div className="photos mini">
          {photoKeys.map((k, i) => (
            <div key={k} className="photo-pos" style={{ left: i * 205, top: i % 2 ? 26 : 0, transform: `rotate(${[-5, 4, -3, 5][i]}deg)` }}>
              <div className="photo" data-in="throw" data-d={6 + i} data-idle="sway">
                <img src={PHOTOS[k].file} alt={PHOTO_TITLES[k]} draggable={false} /><span>{PHOTO_TITLES[k]}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="model-stage" data-in="zoom" data-d={3}>
        <div className="ring ring-b" data-idle="spin-rev" data-speed={40}><i className="dot red" /><i className="dot yellow" /></div>
        {FLAGS.lite
          ? <img className="model-photo" src={PHOTOS["arenes-nimes"].file} alt="" data-idle="float" />
          : <div className="model-host" dangerouslySetInnerHTML={{ __html: MODEL_VIEWER }} />}
        <div className="model-tag"><b>{MODEL.title}</b><span>{typo(T.modelBy(MODEL.author, MODEL.license))}</span></div>
      </div>
      <p className="credits">{`${T.photoCredits} ` + photoKeys.map((k) => `${PHOTO_TITLES[k]} : ${PHOTOS[k].author} (${PHOTOS[k].license})`).join(" · ")}</p>
    </>
  ),
  enter: ({ el }) => {
    const mv = el.querySelector<HTMLElement & { resetTurntableRotation?: (t: number) => void }>("model-viewer");
    if (!mv) return;
    void loadModelViewer().then(() => {
      if (!mv.getAttribute("src")) mv.setAttribute("src", MODEL.file);
      mv.resetTurntableRotation?.(0);
    });
  },
};
