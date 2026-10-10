// Ouverture : intros 3D (courte, puis la première version avec le réseau et les trains), couverture 2D, le constat,
// et l'histoire de Claire en photos puis en 3D low poly.
import { Trame, Words } from "../components/primitives";
import { Net } from "../components/Net";
import { IDEAS } from "../data";
import type { SlideDef } from "../engine/deck";
import { enterNet } from "../engine/net";
import { loadIntro3D, loadStory3D } from "../engine/three";
import { $, fmtMin, html } from "../engine/util";
import { T } from "../textes";

export const intro3d: SlideDef = {
  id: "intro", tone: "dark", cls: "s-3d s-intro", trans: "iris",
  Body: () => (
    <>
      <div className="stage3d" />
      <div className="intro-title">
        <div className="kicker" data-in="flap" data-at={2200}>{T.coverKicker}</div>
        <Words as="h1" className="title huge" data-at={2500} text={T.coverTitle} />
        <Trame rows={3} cols={30} palette={["red", "yellow", "white"]} data-in="trame" data-at={3200} data-idle="drift" />
      </div>
    </>
  ),
  enter: ({ el, t0 }) => void loadIntro3D().then((m) => m.Deck3D.play(el, "intro", t0)),
  leave: (el) => void loadIntro3D().then((m) => m.Deck3D.stop(el)),
};

// La première intro, 10 s : chute depuis le ciel, voies et gares qui se révèlent, petits trains sur tout le réseau
export const intro3dFull: SlideDef = {
  id: "intro-full", tone: "dark", cls: "s-3d s-intro", trans: "flap",
  Body: () => (
    <>
      <div className="stage3d" />
      <div className="intro-title">
        <div className="kicker" data-in="flap" data-at={7400}>{T.coverKicker}</div>
        <Words as="h1" className="title huge" data-at={7900} text={T.coverTitle} />
        <Trame rows={3} cols={30} palette={["red", "yellow", "white"]} data-in="trame" data-at={9000} data-idle="drift" />
      </div>
    </>
  ),
  enter: ({ el, t0 }) => void loadIntro3D().then((m) => m.Deck3D.play(el, "introFull", t0)),
  leave: (el) => void loadIntro3D().then((m) => m.Deck3D.stop(el)),
};

export const cover: SlideDef = {
  id: "cover", tone: "dark", cls: "s-cover", trans: "ter3d",
  Body: () => (
    <>
      <Net kind="cover" />
      <div className="cover-orbit" aria-hidden="true">
        <div className="ring ring-a" data-in="zoom" data-d={2} data-idle="spin" data-speed={60} />
        <div className="ring ring-b" data-in="zoom" data-d={3} data-idle="spin-rev" data-speed={45}><i className="dot red" /><i className="dot yellow" /></div>
        <div className="clock" data-in="pop" data-d={5}><i className="tick-ring" /><i className="hand h" /><i className="hand m" /><i className="hand s" /><i className="pin" /></div>
      </div>
      <div className="cover-text">
        <div className="kicker" data-in="flap" data-d={1}>{T.coverKicker2}</div>
        <Words as="h1" className="title huge" data-d={2} text={T.coverTitle} />
        <p className="lead" data-in="up" data-d={7} dangerouslySetInnerHTML={html(T.coverLead)} />
        <Trame rows={4} cols={30} palette={["red", "yellow", "white"]} data-in="trame" data-d={8} data-idle="drift" />
        <div className="hint" data-in="up" data-d={11} data-idle="bob"><span>{T.coverHint}</span> <kbd>→</kbd></div>
      </div>
    </>
  ),
  enter: ({ el, t0, run }) => {
    enterNet(run, $<SVGSVGElement>(el, ".net-cover:not(.net-ov)"), t0, { draw: 1000 }); // juste la région, sans voies ni gares
    // Horloge de gare à l'heure réelle ; la trotteuse fait le tour en 58,5 s et marque l'arrêt en haut
    const [h, m, s] = [".h", ".m", ".s"].map((c) => $(el, ".hand" + c));
    run.tick(() => {
      const d = new Date(), sec = d.getSeconds() + d.getMilliseconds() / 1000;
      s.style.transform = `rotate(${Math.min(sec / 58.5, 1) * 360}deg)`;
      m.style.transform = `rotate(${d.getMinutes() * 6}deg)`;
      h.style.transform = `rotate(${(d.getHours() % 12) * 30 + d.getMinutes() * 0.5}deg)`;
    });
  },
};

export const problem: SlideDef = {
  id: "problem", tone: "light", cls: "s-problem", trans: "zoom",
  Body: () => (
    <>
      <div className="bignum" data-in="zoom" data-d={1} data-idle="float" aria-hidden="true">13</div>
      <div className="col">
        <div className="kicker" data-in="flap">{T.k1}</div>
        <Words className="title" data-d={1} text={T.problemTitle} />
      </div>
      <Trame className="trame corner" rows={5} cols={24} palette={["red", "yellow", "navy"]} data-in="trame" data-d={4} data-idle="drift" />
    </>
  ),
};

// ── L'histoire de Claire : quatre photos, puis les mêmes quatre scènes en 3D low poly ──
const STORY = [
  { img: "01-prof", kb: "1.02,0,0;1.2,-6,-3", lp: "classe", line: "Claire, prof de CM2, <em>prépare une sortie.</em>" },
  { img: "02-gare", kb: "1.18,4,0;1.05,-4,1", lp: "quai", line: "Mardi, 9 h : <em>28 élèves, un TER.</em>" },
  { img: "03-train", kb: "1.0,0,2;1.22,2,-4", lp: "trajet", line: "Par la fenêtre, <em>le paysage défile.</em>" },
  { img: "04-ville", kb: "1.3,0,-4;1.02,0,0", lp: "ville", line: "59 minutes plus tard : <em>Carcassonne.</em>" },
];
const STORY_TRANS = ["iris", "ter3d", "ter3d-front", "zoom"] as const;
const carca = IDEAS.find((d) => d.city === "Carcassonne");
const carcaTime = carca ? `${fmtMin(carca.minutes)} · ${carca.transfers ? "1 corresp." : "direct"}` : "";

const StoryText = ({ i }: { i: number }) => (
  <div className="story-text">
    <div className="kicker" data-in="flap" data-d={2}>{`L'histoire de Claire · ${i + 1}/4`}</div>
    <Words className="title story-line" data-d={4} text={STORY[i].line} />
  </div>
);
const Pin = ({ at }: { at: number }) => (
  <div className="story-pin" data-in="pop" data-at={at} data-idle="bob"><i className="live" /><b>Carcassonne</b><span>{carcaTime}</span></div>
);

export const storyPhotos: SlideDef[] = STORY.map((s, i) => ({
  id: `story-${i + 1}`, tone: "dark", cls: "s-story", trans: STORY_TRANS[i],
  Body: () => (
    <>
      <div className="story-frame"><img className="story-img" src={`assets/story/${s.img}.jpg`} data-in="kenburns" data-kb={s.kb} alt="" /></div>
      <div className="story-shade" />
      <StoryText i={i} />
      {i === 0 && <div className="story-ui" data-in="throw" data-at={4200} data-idle="float"><img src="assets/story/ui-scolaire.jpg" alt="" /></div>}
      {i === 3 && <Pin at={5200} />}
    </>
  ),
}));

export const storyLowpoly: SlideDef[] = STORY.map((s, i) => ({
  id: `lowpoly-${i + 1}`, tone: "dark", cls: "s-lowpoly", trans: (["iris", "ter3d", "zoom", "ter3d-front"] as const)[i],
  Body: () => (
    <>
      <div className="stage3d" />
      <div className="story-shade soft" />
      <StoryText i={i} />
      {i === 3 && <Pin at={7200} />}
    </>
  ),
  enter: ({ el, t0 }) => void loadStory3D().then((m) => m.DeckStory.play(el, s.lp, t0)),
  leave: (el) => void loadStory3D().then((m) => m.DeckStory.stop(el)),
}));

// La salle des profs, en décor de théâtre (image NanoBanana), sans texte : l'image seule, en zoom lent.
// La scène 3D low poly équivalente existe encore dans three/lowpoly.ts (« salleProfs »), pour y revenir au besoin.
export const staffRoom: SlideDef = {
  id: "salle-profs", tone: "dark", cls: "s-story", trans: "train",
  Body: () => (
    <div className="story-frame"><img className="story-img" src="assets/story/00-salle-profs.jpg" data-in="kenburns" data-kb="1.0,0,0;1.12,0,-2" alt="" /></div>
  ),
};

// Le même théâtre, monté en plateau de conférence (image NanoBanana, même cadrage), sans texte. Scène 3D gardée : « conference ».
export const stage: SlideDef = {
  id: "plateau", tone: "dark", cls: "s-story", trans: "train",
  Body: () => (
    <div className="story-frame"><img className="story-img" src="assets/story/00-conference.jpg" data-in="kenburns" data-kb="1.12,0,-2;1.24,0,-1" alt="" /></div>
  ),
};
