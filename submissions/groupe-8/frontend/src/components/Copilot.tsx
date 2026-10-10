import { useEffect, useRef, useState } from 'react';
import { SUGGESTIONS, answerQuestion } from '../copilot/answers';
import { source } from '../data/source';
import { focusedRec, useStore, stepOf } from '../state/store';

type Msg = { from: 'user' | 'bot'; text: string };

export function Copilot() {
  const request = useStore((s) => s.copilotRequest);
  const onClose = useStore((s) => s.closeCopilot);
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      from: 'bot',
      text: 'Posez une question sur la situation ou sur une recommandation.',
    },
  ]);
  const [thinking, setThinking] = useState(false);
  const [draft, setDraft] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
  }, [msgs, thinking]);

  const ask = async (q: string, recId?: string) => {
    if (!q.trim() || thinking) return;
    setMsgs((m) => [...m, { from: 'user', text: q }]);
    setDraft('');
    setThinking(true);
    const s = useStore.getState();
    const ours = s.timelines!.ours;
    try {
      const text = await answerQuestion(q, {
        snapshot: ours[stepOf(s)],
        focusRecId: recId ?? s.overrideRecId ?? focusedRec(s)?.id,
        finalScore: ours[ours.length - 1].kpis.score,
        finalBaseline: ours[ours.length - 1].kpis.scoreBaseline,
      });
      setMsgs((m) => [...m, { from: 'bot', text }]);
    } finally {
      setThinking(false);
    }
  };

  // "Pourquoi ?" in the focused card opens the panel with that recommendation as subject.
  const handled = useRef(0);
  useEffect(() => {
    if (!request || request.id === handled.current) return;
    handled.current = request.id;
    ask(request.question, request.recId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request]);

  return (
    <section className="copilot">
      <header className="copilot-head">
        <h2>Copilote</h2>
        <span className="tag">{source.ask ? "Connecté au moteur" : "Réponses simulées"}</span>
        <button className="round-close" onClick={onClose} aria-label="Fermer le copilote">
          ×
        </button>
      </header>
      <div className="chat" ref={listRef}>
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.from}`}>
            {m.text}
          </div>
        ))}
        {thinking && (
          <div className="msg bot typing" aria-label="Le copilote répond">
            <i />
            <i />
            <i />
          </div>
        )}
      </div>
      <div className="chips">
        {SUGGESTIONS.map((q) => (
          <button key={q} className="pill small" disabled={thinking} onClick={() => ask(q)}>
            {q}
          </button>
        ))}
      </div>
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          ask(draft);
        }}
      >
        <input className="pill-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Poser une question au copilote…" />
        <button className="pill primary" disabled={!draft.trim() || thinking}>
          Envoyer
        </button>
      </form>
    </section>
  );
}
