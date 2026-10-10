import { useState, type FormEvent } from "react";
import { Check, MessageSquare } from "lucide-react";
import { useAppData } from "../../data/store";
import type { Equipment } from "../../domain/types";
import { Field, Modal } from "../../ui/components";

export function FeedbackForm({
  equipment,
  onClose,
}: {
  equipment: Equipment;
  onClose: () => void;
}) {
  const { saveFeedback } = useAppData();
  const [author, setAuthor] = useState("");
  const [subject, setSubject] = useState("Date ou origine de pose");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await saveFeedback({
        id: crypto.randomUUID(),
        equipmentId: equipment.id,
        subject,
        author: author.trim(),
        comment: comment.trim(),
        createdAt: new Date().toISOString(),
      });
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <Modal
      title="Signaler une information incorrecte"
      description={`${equipment.label} · ${equipment.id}`}
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <div className="context-note">
            <MessageSquare size={17} />
            Votre observation sera conservée dans la fiche pour vérification par
            l’équipe.
          </div>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <Field label="Information concernée">
            <select
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
            >
              {[
                "Date ou origine de pose",
                "Localisation de l’équipement",
                "Prestataire ou contrat",
                "Rattachement d’une demande",
                "Observation d’un rapport",
                "Autre information",
              ].map((label) => (
                <option key={label}>{label}</option>
              ))}
            </select>
          </Field>
          <Field label="Votre nom ou équipe *">
            <input
              required
              autoComplete="name"
              value={author}
              onChange={(event) => setAuthor(event.target.value)}
            />
          </Field>
          <Field
            label="Observation et référence concernée *"
            hint="Indiquez la référence de la demande ou du rapport si nécessaire, et les éléments à vérifier."
          >
            <textarea
              required
              rows={4}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </Field>
          <p className="fine-print">
            Ce signalement conserve les sources originales et le classement
            actuel. Il ne vaut pas validation d’une correction.
          </p>
        </div>
        <div className="modal-footer">
          <button type="button" className="button secondary" onClick={onClose}>
            Annuler
          </button>
          <button className="button primary" type="submit">
            <Check size={17} />
            Enregistrer le signalement
          </button>
        </div>
      </form>
    </Modal>
  );
}
