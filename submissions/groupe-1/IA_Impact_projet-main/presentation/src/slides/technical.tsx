// Sous le capot (les données, le réseau, le moteur, la chaîne technique), puis la suite et la fin.
import type { CSSProperties } from "react";
import { Icon, Trame, Words } from "../components/primitives";
import { Net } from "../components/Net";
import type { SlideDef } from "../engine/deck";
import { STEP } from "../engine/enter";
import { enterNet } from "../engine/net";
import { $, $$, A, fmtMin, html } from "../engine/util";
import { T } from "../textes";

export const data: SlideDef = {
  id: "data", tone: "light", cls: "s-data", trans: "ter3d",
  Body: () => (
    <>
      <div className="kicker" data-in="flap">{T.dataKick}</div>
      <Words className="title" data-d={1} text={T.dataTitle} />
      <div className="stats">
        {([[5050, T.dstat1], [3381, T.dstat2], [12085, T.dstat3], [345, T.dstat4]] as const).map(([n, label], i) => (
          <div key={label} className="stat" data-in="up" data-d={4 + i}><b data-count={n} /><span>{label}</span></div>
        ))}
      </div>
      <div className="dataset" data-in="mask" data-d={9}><span className="tag">{T.datasetTag}</span><span dangerouslySetInnerHTML={html(T.dataset)} /></div>
      <div className="sources">
        {["GTFS SNCF · TGV, Intercités, TER", "GTFS liO · Région Occitanie", T.src3, "transport.data.gouv.fr"].map((s, i) => (
          <span key={s} className="chip" data-in="pop" data-d={10 + i} data-idle="bob">{s}</span>
        ))}
      </div>
      <p className="foot" data-in="up" data-d={14} dangerouslySetInnerHTML={html(T.dataFoot)} />
    </>
  ),
};

export const network: SlideDef = {
  id: "network", tone: "dark", cls: "s-network", trans: "cube",
  Body: () => (
    <>
      <div className="col">
        <div className="kicker" data-in="flap">{T.stepsKick}</div>
        <Words className="title" data-d={1} text={T.stepsTitle} />
        <ol className="steps">
          {[T.step1, T.step2, T.step3].map((s, i) => <li key={i} data-in="left" data-d={5 + i}><i>{i + 1}</i><span dangerouslySetInnerHTML={html(s)} /></li>)}
        </ol>
      </div>
      <Net kind="map" />
    </>
  ),
  enter: ({ el, t0, run }) => enterNet(run, $<SVGSVGElement>(el, ".net-map:not(.net-ov)"), t0 + 300, { draw: 2400, trains: 14 }),
};

// 09 · Fiable : les chiffres du réseau à côté de la carte, où circulent les petits trains
export const reliable: SlideDef = {
  id: "reliable", tone: "dark", cls: "s-network", trans: "zoom",
  Body: () => (
    <>
      <div className="col">
        <div className="kicker" data-in="flap">{T.k9}</div>
        <Words className="title" data-d={1} text={T.networkTitle} />
        <div className="stats small">
          <div className="stat" data-in="up" data-d={4}><b data-count={259} /><span>{T.stat1}</span></div>
          <div className="stat" data-in="up" data-d={5}><b data-count={403} /><span>{T.stat2}</span></div>
        </div>
      </div>
      <Net kind="map" />
    </>
  ),
  enter: ({ el, t0, run }) => enterNet(run, $<SVGSVGElement>(el, ".net-map:not(.net-ov)"), t0 + 300, { draw: 2400, trains: 14 }),
};

// Attente moyenne selon la fréquence. La piste couvre 4 h : points = trains, barre rouge = attente
const WINDOW = 240, TRACK = 1150, PX_MIN = TRACK / WINDOW;
const waitOf = (n: number) => Math.min(960 / (2 * n), 120);

export const engine: SlideDef = {
  id: "engine", tone: "light", cls: "s-engine", trans: "zoom",
  Body: () => (
    <>
      <div className="kicker" data-in="flap">{T.engineKick}</div>
      <Words className="title" data-d={1} text={T.engineTitle} />
      <p className="lead dark-ink" data-in="up" data-d={4} dangerouslySetInnerHTML={html(T.engineLead)} />
      <div className="formula">
        <div className="term t-ride" data-in="mask" data-d={6}><b>{T.fRide}</b><small>{T.fRideSub}</small></div>
        <div className="op" data-in="pop" data-d={7}>+</div>
        <div className="term t-sum" data-in="pop" data-d={8}><b>Σ</b><small>{T.fChanges}</small></div>
        <div className="paren" data-in="mask" data-d={9}>
          <div className="term t-change" data-idle="bob"><b>5 min</b><small>{T.fChange}</small></div>
          <div className="op">+</div>
          <div className="term t-wait" data-idle="bob"><b>{T.fWait}</b><small>{T.fWaitSub}</small></div>
        </div>
      </div>
      <div className="waits">
        <div className="waits-title" data-in="up" data-d={11}>{T.waitsTitle}</div>
        <div className="wait-rows">
          {[2, 7, 17, 34].map((n, i) => (
            <div key={n} className="wait-row" data-in="left" data-d={12 + i}>
              <span>{T.waitRow(n)}</span>
              <div className="wait-track">
                <div className="wait-bar" style={{ width: `${(waitOf(n) / WINDOW) * 100}%` }} />
                <div className="wait-dots" style={{ "--gap": `${(960 / n) * PX_MIN}px` } as CSSProperties} data-headway={960 / n} />
              </div>
              <b>{fmtMin(waitOf(n))}</b>
            </div>
          ))}
        </div>
      </div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    $$(el, ".wait-row").forEach((row, i) => {
      const d = t0 + (12 + i) * STEP + 400;
      A($(row, ".wait-bar"), [{ transform: "scaleX(0)" }, { transform: "none" }], { duration: 1100, delay: d });
      const dots = $(row, ".wait-dots"), gap = parseFloat(dots.style.getPropertyValue("--gap"));
      // Les trains défilent à vitesse constante : plus ils sont fréquents, plus ils sont serrés
      run.later(d, () => dots.animate({ translate: ["0 0", `${-gap}px 0`] }, { duration: +(dots.dataset.headway ?? 1) * 30, iterations: Infinity }));
    });
  },
};

export const stack: SlideDef = {
  id: "stack", tone: "dark", cls: "s-stack", trans: "ter3d-front",
  Body: () => {
    const nodes = [
      ["cube", T.p1, T.p1s], ["code", T.p2, "build_from_gtfs.py · ~2 s"], ["bolt", "FastAPI", "/route · /places · /network"],
      ["map", "React + MapLibre", T.p4s], ["ter", "three.js", T.p5s],
    ] as const;
    return (
      <>
        <div className="kicker" data-in="flap">{T.stackKick}</div>
        <Words className="title" data-d={1} text={T.stackTitle} />
        <div className="pipeline">
          <svg className="rail" viewBox="0 0 1600 40" preserveAspectRatio="none" aria-hidden="true"><path d="M20 20H1580" data-in="draw" data-d={4} /></svg>
          {nodes.map(([ico, title, sub], i) => (
            <div key={title} className="node" data-in="pop" data-d={5 + i}>
              <div className="node-in" data-idle="float"><i className="n-ico"><Icon name={ico} /></i><b>{title}</b><small>{sub}</small></div>
            </div>
          ))}
          <i className="runner" />
        </div>
        <p className="lead" data-in="up" data-d={11} dangerouslySetInnerHTML={html(T.stackLead)} />
      </>
    );
  },
  enter: ({ el, t0, run }) => {
    const runner = $(el, ".runner");
    run.later(t0 + 1800, () => runner.animate(
      [{ transform: "translateX(0)", opacity: 0 }, { opacity: 1, offset: 0.08 }, { opacity: 1, offset: 0.92 }, { transform: "translateX(1570px)", opacity: 0 }],
      { duration: 4200, iterations: Infinity, easing: "cubic-bezier(.45,0,.55,1)" }));
  },
};

export const next: SlideDef = {
  id: "next", tone: "light", cls: "s-next", trans: "push",
  Body: () => (
    <>
      <div className="kicker" data-in="flap">{T.nextKick}</div>
      <Words className="title" data-d={1} text={T.nextTitle} />
      <div className="roadmap">
        {([[T.n1, T.n1s], [T.n2, T.n2s], [T.n3, T.n3s], [T.n4, T.n4s]] as const).map(([title, sub], i) => (
          <div key={title} className="road" data-in="right" data-d={4 + i}>
            <span className="num" data-idle="wheel">{String(i + 1).padStart(2, "0")}</span>
            <div><b>{title}</b><p dangerouslySetInnerHTML={html(sub)} /></div>
          </div>
        ))}
      </div>
    </>
  ),
};

export const thanks: SlideDef = {
  id: "thanks", tone: "red-bg", cls: "s-thanks", trans: "train",
  Body: () => (
    <>
      <div className="cover-orbit thanks-orbit" aria-hidden="true">
        <div className="ring ring-a" data-in="zoom" data-d={1} data-idle="spin" data-speed={50} />
        <div className="ring ring-b" data-in="zoom" data-d={2} data-idle="spin-rev" data-speed={35}><i className="dot yellow" /><i className="dot navy" /></div>
      </div>
      <Words className="title huge" data-d={2} text={T.thanksTitle} />
      <p className="lead" data-in="up" data-d={5} dangerouslySetInnerHTML={html(T.thanksLead)} />
      <Trame rows={3} cols={34} palette={["yellow", "white", "navy"]} data-in="trame" data-d={6} data-idle="drift" />
    </>
  ),
};

// Slide vierge : un temps blanc, amené par le TER dessiné en 2D qui traverse l'écran (à remplir plus tard)
export const blank: SlideDef = { id: "vierge", tone: "light", cls: "s-blank", trans: "train", Body: () => <></> };

// Fin du diapo : le QR code du site, à scanner depuis la salle
export const qr: SlideDef = {
  id: "qr", tone: "red-bg", cls: "s-qr", trans: "train",
  Body: () => (
    <>
      <div className="qr-text">
        <Words className="title huge" data-d={2} text={T.qrTitle} />
        <p className="lead" data-in="up" data-d={5} dangerouslySetInnerHTML={html(T.qrLead)} />
        <Trame rows={3} cols={20} palette={["yellow", "white", "navy"]} data-in="trame" data-d={6} data-idle="drift" />
      </div>
      <div className="qr-card" data-in="pop" data-d={4} data-idle="float"><img src="assets/qr-ia-impact.png" alt={T.qrAlt} /></div>
    </>
  ),
};
