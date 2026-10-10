// Le diapo : une scène fixe 1920 × 1080 mise à l'échelle de l'écran, les slides empilées dessus, le calque
// des transitions et les commandes. React rend le contenu une fois ; le moteur (engine/) anime ensuite le DOM
// directement — c'est ce qui garde les animations fluides (aucun rendu React pendant un mouvement).
import { memo, useEffect, useRef, useState } from "react";
import { DeckEngine, type SlideDef } from "../engine/deck";
import { loadIntro3D } from "../engine/three";
import { FLAGS, H, W } from "../engine/util";
import { Controls, useFullscreen } from "./Controls";

const Slides = memo(function Slides({ slides, refs }: { slides: SlideDef[]; refs: React.MutableRefObject<(HTMLElement | null)[]> }) {
  return (
    <>
      {slides.map((s, i) => (
        <section key={s.id} ref={(el) => { refs.current[i] = el; }} className={`slide ${s.tone} ${s.cls}`} data-slide={s.id}>
          <s.Body />
          <i className="rails" />
        </section>
      ))}
    </>
  );
});

export function Deck({ slides }: { slides: SlideDef[] }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const layerRef = useRef<HTMLDivElement>(null);
  const slideRefs = useRef<(HTMLElement | null)[]>([]);
  const [engine, setEngine] = useState<DeckEngine | null>(null);
  const fs = useFullscreen();

  // Mise à l'échelle de la scène
  useEffect(() => {
    const fit = () => {
      const k = Math.min(innerWidth / W, innerHeight / H);
      if (stageRef.current) stageRef.current.style.transform = `scale(${k}) translate(-50%, -50%)`;
    };
    fit();
    addEventListener("resize", fit);
    return () => removeEventListener("resize", fit);
  }, []);

  // Moteur : créé une fois les slides dans le DOM
  useEffect(() => {
    const stage = stageRef.current!, layer = layerRef.current!;
    const els = slideRefs.current.slice(0, slides.length).map((el, i) => ({ el: el!, def: slides[i] }));
    const eng = new DeckEngine(els, stage, layer);
    setEngine(eng);
    if (!FLAGS.lite && slides.some((s) => s.id === "intro")) loadIntro3D(); // three.js se télécharge pendant qu'on regarde

    // Images décodées d'avance : la première apparition d'une photo ne décode plus un JPEG en pleine animation
    stage.querySelectorAll("img").forEach((img) => img.decode?.().catch(() => {}));

    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (["ArrowRight", "ArrowDown", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); eng.next(); }
      else if (["ArrowLeft", "ArrowUp", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); eng.prev(); }
      else if (e.key === "Home") eng.go(0);
      else if (e.key === "End") eng.go(slides.length - 1);
      else if (e.key === "f" || e.key === "F") fs.toggle();
    };
    // Clic = suivante ; glisser au doigt = suivante / précédente
    let downX: number | null = null;
    const onDown = (e: PointerEvent) => (downX = e.clientX);
    const onUp = (e: PointerEvent) => {
      if (downX == null) return;
      const dx = e.clientX - downX; downX = null;
      if (Math.abs(dx) > 50) (dx < 0 ? eng.next : eng.prev)();
      else if (Math.abs(dx) < 8) eng.next();
    };
    document.addEventListener("keydown", onKey);
    stage.addEventListener("pointerdown", onDown);
    stage.addEventListener("pointerup", onUp);

    let alive = true;
    const startAt = parseInt(location.hash.slice(1), 10);
    document.fonts.ready.then(() => alive && eng.go(Number.isFinite(startAt) ? startAt - 1 : 0));

    return () => {
      alive = false;
      document.removeEventListener("keydown", onKey);
      stage.removeEventListener("pointerdown", onDown);
      stage.removeEventListener("pointerup", onUp);
      eng.destroy();
    };
    // fs.toggle ne dépend d'aucun état : inutile de recréer le moteur quand le plein écran change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slides]);

  return (
    <div className="deck">
      <div className="stage" ref={stageRef}>
        <Slides slides={slides} refs={slideRefs} />
        <div className="streaks" ref={layerRef} aria-hidden="true" />
      </div>
      {engine && <Controls engine={engine} fs={fs} />}
    </div>
  );
}
