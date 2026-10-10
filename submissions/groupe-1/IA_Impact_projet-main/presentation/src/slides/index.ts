// L'ordre du diapo. Une slide retirée ici disparaît du diapo (son code reste dans son fichier).
import type { SlideDef } from "../engine/deck";
import { FLAGS } from "../engine/util";
import { cover, intro3d, intro3dFull, problem, stage, staffRoom, storyLowpoly, storyPhotos } from "./opening";
import {
  assistant, discover, follow3d, overview, route, school, search, sim, solution,
  videoPlaces, videoRoute, videoSchool, videoSim, windowSlide,
} from "./features";
import { blank, data, engine, network, next, qr, reliable, stack, thanks } from "./technical";

// ?lite : sans les scènes WebGL (intros, « Suivez le train », histoire low poly ; transitions TER 3D remplacées en 2D)
const gl = (...s: SlideDef[]) => (FLAGS.lite ? [] : s);

// Reconstruction slide par slide : les lignes commentées attendent d'être remises.
export const SLIDES: SlideDef[] = [
  staffRoom,
  stage,
  // ...gl(intro3d, intro3dFull),
  // cover,
  // problem,
  // ...storyPhotos,
  // ...gl(...storyLowpoly),
  // solution,
  // overview,
  // search,
  // videoRoute,
  // route,
  // sim,
  // videoSim,
  // windowSlide,
  // ...gl(follow3d),
  // discover,
  // videoPlaces,
  // school,
  // videoSchool,
  // assistant,
  // data,
  // network,
  // engine,
  // stack,
  // reliable,
  // next,
  // thanks,
  blank,
  qr,
];

// Le stock des slides en attente (garde les imports vivants tant qu'elles sont retirées du diapo)
export const BENCH = {
  intro3d, intro3dFull, cover, problem, storyPhotos, storyLowpoly, solution, overview, search,
  videoRoute, route, sim, videoSim, windowSlide, follow3d, discover, videoPlaces, school,
  videoSchool, assistant, data, network, engine, stack, reliable, next, thanks, gl,
};
