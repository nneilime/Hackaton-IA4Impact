import { useRef } from "react";
import type { Place } from "../api";
import { useI18n } from "../i18n";
import type { Discovery } from "../data/discoveries";
import type { Recommendations } from "../recommendations";
import { DiscoveryImage } from "./Discovery";
import { useBottomHeight } from "./SimPanel";
import { toClock } from "../reliability";
import { scheduleOf, type Proposal } from "../school";

type Props = {
  recos: Recommendations;
  byId: Map<string, Place>;
  onChoose: (p: Proposal) => void;
  onOpenDiscovery: (d: Discovery) => void;
  onClose: () => void;
};

// Bandeau du bas quand aucune simulation ne l'occupe : les lieux recommandés (projet scolaire, assistant IA),
// mêmes cartes que « à voir autour du train ». Toujours déplié : les idées trouvées restent sous les yeux jusqu'à
// ce qu'on ferme le bandeau.
export default function RecoPanel({ recos, byId, onChoose, onOpenDiscovery, onClose }: Props) {
  const { t, locale } = useI18n();
  const root = useRef<HTMLElement>(null);
  useBottomHeight(root);
  const { items } = recos;

  return (
    <section ref={root} className="sim reco open" aria-label={t.recoTitle[recos.source]}>
      <div className="sim-head">
        <div className="sim-toggle">
          <span className="reco-dot" aria-hidden="true" />
          <span className="sim-title">{t.recoTitle[recos.source]}</span>
          <span className="sim-clock">{t.recoCount(items.length)}</span>
        </div>
        <button className="sim-close" onClick={onClose} aria-label={t.close} title={t.close}>
          ×
        </button>
      </div>

      <div className="sim-body">
        <div className="sim-inner">
          {items.length > 0 ? (
            <ul className="sim-list">
              {items.map(({ discovery: d, proposal: p, reason }) => (
                <li key={d.id}>
                  <button onClick={() => (p ? onChoose(p) : onOpenDiscovery(d))}>
                    <DiscoveryImage d={d} />
                    <span>
                      <span className="sim-km">{byId.get(d.stationId)?.commune ?? byId.get(d.stationId)?.name}</span>
                      <strong>{d.title[locale]}</strong>
                      {p ? <ProposalTimes p={p} /> : null}
                      <span className="sim-summary">{reason ?? d.summary[locale]}</span>
                      <span className="reco-go">{p ? t.schoolSee : t.learnMore} →</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">{recos.source === "school" ? t.schoolEmpty : t.recoNone}</p>
          )}
        </div>
      </div>
    </section>
  );
}

function ProposalTimes({ p }: { p: Proposal }) {
  const { t } = useI18n();
  const { out, back } = scheduleOf(p);
  return (
    <span className="reco-meta">
      {t.schoolOut} <b>{toClock(out.minute)}</b> → {toClock(out.arrival)} ·{" "}
      {back && (
        <>
          {t.schoolBack} <b>{toClock(back.minute)}</b> → {toClock(back.arrival)} ·{" "}
        </>
      )}
      {p.outbound.transfers ? t.transfers(p.outbound.transfers) : t.direct}
    </span>
  );
}
