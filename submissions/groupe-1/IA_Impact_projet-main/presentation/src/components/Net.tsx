// Carte du réseau liO en SVG : contour de l'Occitanie, voies, gares (et noms des grandes villes sur la carte
// « map »). Un second SVG superposé, sur sa propre couche, reçoit ce qui bouge (voir engine/net.ts).
import { NETWORK, ST } from "../data";

export type NetKind = "cover" | "route" | "sim" | "map";

const LABELS: Record<string, string> = { "87611004": "Toulouse", "87773002": "Montpellier", "87784009": "Perpignan", "87775007": "Nîmes", "87613422": "Rodez", "87615005": "Albi", "87781005": "Béziers" };
const BIG = new Set(Object.values(NETWORK.ids));
// Tronçons triés de gauche à droite : le tracé se lit dans le sens de la lecture
const EDGES_D = NETWORK.edges.slice()
  .sort((e, f) => Math.min(ST[e[0]][0], ST[e[1]][0]) - Math.min(ST[f[0]][0], ST[f[1]][0]))
  .map(([a, b]) => `M${ST[a][0]} ${ST[a][1]}L${ST[b][0]} ${ST[b][1]}`).join("");

export function Net({ kind }: { kind: NetKind }) {
  const cls = `net net-${kind}`;
  return (
    <>
      <svg className={cls} viewBox="0 0 1000 820" data-net={kind}>
        <path className="outline" pathLength={1} d={NETWORK.outline} />
        <path className="edges" pathLength={1} d={EDGES_D} />
        <g className="sts">
          {ST.map(([x, y], i) => <circle key={i} className={BIG.has(i) ? "st big" : "st"} cx={x} cy={y} r={BIG.has(i) ? 8 : 4} />)}
        </g>
        <g className="extra" />
        <g className="lbls">
          {kind === "map" && Object.entries(LABELS).map(([id, name]) => {
            const [x, y] = ST[NETWORK.ids[id]];
            return <text key={id} className="lbl" x={x + 14} y={y + 7}>{name}</text>;
          })}
        </g>
      </svg>
      <svg className={`${cls} net-ov`} viewBox="0 0 1000 820" aria-hidden="true">
        <g className="trains" />
        <g className="movers" />
      </svg>
    </>
  );
}
