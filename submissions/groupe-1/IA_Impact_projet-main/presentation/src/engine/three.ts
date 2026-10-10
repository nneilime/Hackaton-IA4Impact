// Chargement à la demande des scènes three.js : le code 3D (et three lui-même) n'est téléchargé que si une
// slide 3D est au programme, et une seule fois.
type Scene3DModule = typeof import("../three/scene3d");
let intro: Promise<Scene3DModule> | null = null;
let story: Promise<typeof import("../three/lowpoly")> | null = null;

/** Module 3D de la carte une fois chargé : les transitions TER 3D s'en servent sans attendre (sinon repli en 2D) */
export let deck3d: Scene3DModule["Deck3D"] | null = null;

export const loadIntro3D = () => (intro ??= import("../three/scene3d").then((m) => ((deck3d = m.Deck3D), m)));
export const loadStory3D = () => (story ??= import("../three/lowpoly"));

// <model-viewer> (Google, avec son propre three.js) : chargé une fois, à la première slide qui montre un monument.
// Les modèles du site sont compressés en meshopt : le décodeur doit être connu avant de charger un modèle.
let mv: Promise<void> | null = null;
export const loadModelViewer = () => (mv ??= new Promise<void>((ok) => {
  const s = document.createElement("script");
  s.type = "module"; s.src = "vendor/model-viewer.min.js";
  document.head.append(s);
  customElements.whenDefined("model-viewer").then((C) => {
    (C as unknown as { meshoptDecoderLocation: string }).meshoptDecoderLocation = new URL("vendor/meshopt_decoder.js", location.href).href;
    ok();
  });
}));
