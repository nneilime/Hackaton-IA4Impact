import { Injectable, WritableSignal, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay } from 'rxjs';
import { Decision, FactureDetail, FactureResume } from '../models/invoice.model';

/** File de contrôle de l'agent : factures analysées par l'OCR, en anomalie (KO ou À vérifier) et sans décision, dans l'ordre de l'API. */
@Injectable({
  providedIn: 'root'
})
export class InvoiceService {
  private http = inject(HttpClient);
  private details = new Map<string, Observable<FactureDetail>>();

  public queue = signal<FactureResume[]>([]);
  public currentInvoiceIndex = signal<number>(0);
  public currentInvoice = signal<FactureDetail | null>(null);
  public loading = signal<boolean>(true);
  public saving = signal<boolean>(false);
  public error = signal<string | null>(null);

  public validatedInvoices = signal<string[]>([]);
  public rejectedInvoices = signal<string[]>([]);

  /** Difficulté maximale que l'agent accepte de voir (curseur, 0–100, 100 = tout voir) */
  public difficulteMax = signal<number>(100);
  /** Dernière liste brute reçue de l'API (avant filtre de difficulté) */
  private toutes = signal<FactureResume[]>([]);
  /** Factures éligibles masquées uniquement par le filtre de difficulté */
  public nbMasquees = computed(() => {
    const max = this.difficulteMax();
    const decided = new Set([...this.validatedInvoices(), ...this.rejectedInvoices()]);
    return this.toutes().filter(f => this.eligible(f) && !decided.has(f.id) && this.difficulte(f) > max).length;
  });

  /** File épuisée : l'agent attend les factures que l'OCR va ajouter (page d'attente, pas de récapitulatif) */
  public isFinished = computed(() => !this.loading() && this.currentInvoiceIndex() >= this.queue().length);

  /** Délai entre deux interrogations de l'API tant que le lot OCR du backend n'est pas terminé */
  static POLL_MS = 15_000;
  private pollTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.load();
  }

  /** (Re)charge la file depuis le début. */
  load() {
    clearTimeout(this.pollTimer);
    this.loading.set(true);
    this.error.set(null);
    this.http.get<FactureResume[]>('/api/factures').subscribe({
      next: list => {
        this.toutes.set(list);
        this.queue.set(this.toReview(list));
        this.currentInvoiceIndex.set(0);
        this.loading.set(false);
        this.showCurrent();
        this.schedulePoll(list);
      },
      error: () => {
        this.error.set('Impossible de charger les factures. Vérifiez que le backend est démarré.');
        this.loading.set(false);
      },
    });
  }

  /** Difficulté avec repli à 100 (invoices sans score : toujours visibles) */
  private difficulte(f: FactureResume) {
    return f.difficulte ?? 100;
  }

  private eligible(f: FactureResume) {
    return f.ocr && !f.traitee && (f.nb_ko > 0 || f.nb_a_verifier > 0);
  }

  /** Factures à montrer à l'agent : analysées par l'OCR, sans décision, avec au moins un KO ou À vérifier, sous la difficulté max */
  private toReview(list: FactureResume[]) {
    return list.filter(f => this.eligible(f) && this.difficulte(f) <= this.difficulteMax());
  }

  /** Change le curseur de difficulté max et reconstruit la file sans perdre la facture en cours. */
  setDifficulteMax(v: number) {
    this.difficulteMax.set(v);
    const curId = this.currentInvoice()?.id;
    const filtered = this.toReview(this.toutes());
    if (curId && !filtered.some(f => f.id === curId)) {
      // La facture à l'écran dépasse le nouveau max : on la garde à sa place jusqu'à sa décision.
      const resume = this.toutes().find(f => f.id === curId) ?? this.queue().find(f => f.id === curId);
      if (resume && this.queue().some(f => f.id === curId)) {
        const idx = Math.min(this.currentInvoiceIndex(), filtered.length);
        this.queue.set([...filtered.slice(0, idx), resume, ...filtered.slice(idx)]);
        this.currentInvoiceIndex.set(idx);
        return;
      }
    }
    this.queue.set(filtered);
    if (curId) {
      const at = filtered.findIndex(f => f.id === curId);
      if (at >= 0) this.currentInvoiceIndex.set(at);
      else {
        this.currentInvoiceIndex.set(Math.min(this.currentInvoiceIndex(), Math.max(0, filtered.length - 1)));
        this.showCurrent();
      }
    } else {
      this.currentInvoiceIndex.set(0);
      this.showCurrent();
    }
  }

  resetDifficulteMax() {
    this.setDifficulteMax(100);
  }

  /** Tant que l'OCR analyse des scans, revient chercher les nouvelles factures. */
  private schedulePoll(list: FactureResume[]) {
    if (list.some(f => !f.ocr)) {
      this.pollTimer = setTimeout(() => this.poll(), InvoiceService.POLL_MS);
    }
  }

  /** Ajoute en fin de file les factures nouvellement analysées, sans toucher à celle en cours. */
  private poll() {
    this.http.get<FactureResume[]>('/api/factures').subscribe({
      next: list => {
        this.toutes.set(list);
        const known = new Set(this.queue().map(f => f.id));
        const added = this.toReview(list).filter(f => !known.has(f.id));
        if (added.length) {
          const wasAtEnd = this.currentInvoiceIndex() >= this.queue().length;
          const wasLast = this.currentInvoiceIndex() === this.queue().length - 1;
          this.queue.update(q => [...q, ...added]);
          if (wasAtEnd) this.showCurrent(); // the agent was waiting: show the new invoice right away
          else if (wasLast) this.preload(added[0].id);
        }
        this.schedulePoll(list);
      },
      error: () => {
        this.pollTimer = setTimeout(() => this.poll(), InvoiceService.POLL_MS); // backend restarting: try again
      },
    });
  }

  validateCurrent() {
    this.decide({ statut: 'valide', commentaire: '', overrides: [] }, this.validatedInvoices);
  }

  rejectCurrent() {
    this.decide({ statut: 'rejete', commentaire: '', overrides: [] }, this.rejectedInvoices);
  }

  private decide(decision: Decision, done: WritableSignal<string[]>) {
    const current = this.currentInvoice();
    if (!current || this.saving()) return;
    this.saving.set(true);
    this.http.post<void>(`/api/factures/${current.id}/decision`, decision).subscribe({
      next: () => {
        this.saving.set(false);
        done.update(list => [...list, current.id]);
        // La facture décidée sort de la file (y compris si elle y était gardée au-delà
        // du filtre de difficulté) : la suivante glisse à sa place, sans recharger.
        this.queue.update(q => q.filter(f => f.id !== current.id));
        this.currentInvoiceIndex.set(Math.min(this.currentInvoiceIndex(), Math.max(0, this.queue().length - 1)));
        this.showCurrent();
      },
      error: () => {
        this.saving.set(false);
        this.error.set(`La décision sur ${current.id} n'a pas été enregistrée. Réessayez.`);
      },
    });
  }

  /** Charge la facture courante et précharge la suivante (JSON + image) pour un enchaînement instantané. */
  private showCurrent() {
    const queue = this.queue();
    const i = this.currentInvoiceIndex();
    this.currentInvoice.set(null);
    if (i >= queue.length) return;
    this.error.set(null);
    const id = queue[i].id;
    this.fetch(id).subscribe({
      next: d => {
        if (this.queue()[this.currentInvoiceIndex()]?.id === id) this.currentInvoice.set(d);
      },
      error: () => this.error.set(`Impossible de charger la facture ${id}.`),
    });
    const next = queue[i + 1];
    if (next) this.preload(next.id);
  }

  private preload(id: string) {
    this.fetch(id).subscribe({ next: d => (new Image().src = d.image.url), error: () => {} });
  }

  private fetch(id: string): Observable<FactureDetail> {
    let req = this.details.get(id);
    if (!req) {
      req = this.http.get<FactureDetail>(`/api/factures/${id}`).pipe(shareReplay(1));
      this.details.set(id, req);
    }
    return req;
  }
}
