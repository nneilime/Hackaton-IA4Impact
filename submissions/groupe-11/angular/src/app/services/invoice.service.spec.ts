import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { InvoiceService } from './invoice.service';
import { FactureDetail, FactureResume } from '../models/invoice.model';

const detail = (id: string, difficulte = 8): FactureDetail => ({
  id,
  image: { url: `/api/images/${id}.jpg`, largeur: 1190, hauteur: 1684 },
  checks: [{ code: 'C14', libelle: 'Signatures', statut: 'KO', attendu: 'a', lu: 'b', zones: [9, 11], boxes: [[1, 2, 3, 4]], confiance: 1.0 }],
  traitee: false,
  difficulte,
  niveau: 'Facile',
});

const resume = (id: string, difficulte = 8, nb_ko = 1): FactureResume => ({
  id, nb_ko, nb_a_verifier: 0, ocr: true, traitee: false, difficulte, niveau: 'Facile',
});

describe('InvoiceService', () => {
  let service: InvoiceService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(InvoiceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('queues only OCR-analysed, undecided invoices with an anomaly, then posts decisions and moves on', () => {
    const list: FactureResume[] = [
      resume('Facture1_01'),
      { ...resume('Facture1_02'), nb_ko: 0, nb_a_verifier: 2 },
      { ...resume('Facture1_03'), nb_ko: 0, nb_a_verifier: 0 },
      { ...resume('Facture1_05', 68), nb_ko: 0, nb_a_verifier: 17, ocr: false }, // scan not OCR'd yet
      { ...resume('Facture1_04'), traitee: true },
    ];
    http.expectOne('/api/factures').flush(list);
    expect(service.queue().map(f => f.id)).toEqual(['Facture1_01', 'Facture1_02']);

    http.expectOne('/api/factures/Facture1_01').flush(detail('Facture1_01'));
    http.expectOne('/api/factures/Facture1_02').flush(detail('Facture1_02')); // preload
    expect(service.currentInvoice()?.id).toBe('Facture1_01');

    service.rejectCurrent();
    const post = http.expectOne('/api/factures/Facture1_01/decision');
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ statut: 'rejete', commentaire: '', overrides: [] });
    post.flush(null, { status: 204, statusText: 'No Content' });

    expect(service.rejectedInvoices()).toEqual(['Facture1_01']);
    expect(service.currentInvoice()?.id).toBe('Facture1_02'); // served from the preload, no new GET

    service.validateCurrent();
    http.expectOne('/api/factures/Facture1_02/decision').flush(null, { status: 204, statusText: 'No Content' });
    expect(service.isFinished()).toBe(true);
  });

  it('stays on the invoice when the decision cannot be saved', () => {
    http.expectOne('/api/factures').flush([resume('Facture1_01')]);
    http.expectOne('/api/factures/Facture1_01').flush(detail('Facture1_01'));

    service.validateCurrent();
    http.expectOne('/api/factures/Facture1_01/decision').flush('boom', { status: 500, statusText: 'Error' });

    expect(service.currentInvoice()?.id).toBe('Facture1_01');
    expect(service.validatedInvoices()).toEqual([]);
    expect(service.error()).toContain('Facture1_01');
  });

  it('is empty when no invoice has been analysed by the OCR yet', () => {
    http.expectOne('/api/factures').flush([{ ...resume('Facture1_02', 68), nb_ko: 0, nb_a_verifier: 17, ocr: false }]);
    expect(service.queue()).toEqual([]);
    expect(service.currentInvoice()).toBeNull();
    expect(service.isFinished()).toBe(true); // waiting page
  });

  it('appends invoices as the OCR batch analyses them, without reloading or moving the agent', () => {
    vi.useFakeTimers();
    try {
      const f = (id: string, ocr: boolean, nb_ko = 1) => ({ ...resume(id, 8, nb_ko), ocr });
      http.expectOne('/api/factures').flush([f('Facture1_01', true), f('Facture1_02', false), f('Facture1_03', false)]);
      http.expectOne('/api/factures/Facture1_01').flush(detail('Facture1_01'));
      expect(service.currentInvoice()?.id).toBe('Facture1_01');

      // Facture1_02 gets analysed while the agent is on Facture1_01: queued behind it, preloaded
      vi.advanceTimersByTime(InvoiceService.POLL_MS);
      http.expectOne('/api/factures').flush([f('Facture1_01', true), f('Facture1_02', true), f('Facture1_03', false)]);
      expect(service.queue().map(q => q.id)).toEqual(['Facture1_01', 'Facture1_02']);
      expect(service.currentInvoice()?.id).toBe('Facture1_01');
      expect(service.loading()).toBe(false);
      http.expectOne('/api/factures/Facture1_02').flush(detail('Facture1_02'));

      service.validateCurrent();
      http.expectOne('/api/factures/Facture1_01/decision').flush(null, { status: 204, statusText: 'No Content' });
      service.validateCurrent();
      http.expectOne('/api/factures/Facture1_02/decision').flush(null, { status: 204, statusText: 'No Content' });
      expect(service.isFinished()).toBe(true);

      // The agent is waiting at the end of the queue: the next analysed invoice is shown right away
      vi.advanceTimersByTime(InvoiceService.POLL_MS);
      http.expectOne('/api/factures').flush([
        { ...f('Facture1_01', true), traitee: true },
        { ...f('Facture1_02', true), traitee: true },
        f('Facture1_03', true),
      ]);
      http.expectOne('/api/factures/Facture1_03').flush(detail('Facture1_03'));
      expect(service.isFinished()).toBe(false);
      expect(service.currentInvoice()?.id).toBe('Facture1_03');

      // Every scan is analysed: no more polling
      vi.advanceTimersByTime(InvoiceService.POLL_MS * 2);
      http.expectNone('/api/factures');
    } finally {
      vi.useRealTimers();
    }
  });

  it('filters the queue by max difficulty without losing the invoice on screen', () => {
    http.expectOne('/api/factures').flush([resume('Facture1_01', 8), resume('Facture1_02', 48), resume('Facture1_03', 24)]);
    http.expectOne('/api/factures/Facture1_01').flush(detail('Facture1_01'));
    http.expectOne('/api/factures/Facture1_02').flush(detail('Facture1_02', 48)); // preload
    expect(service.difficulteMax()).toBe(100);
    expect(service.nbMasquees()).toBe(0);

    service.setDifficulteMax(30);
    expect(service.queue().map(f => f.id)).toEqual(['Facture1_01', 'Facture1_03']);
    expect(service.nbMasquees()).toBe(1);
    expect(service.currentInvoice()?.id).toBe('Facture1_01'); // still on screen, no reload

    service.resetDifficulteMax();
    expect(service.difficulteMax()).toBe(100);
    expect(service.queue().map(f => f.id)).toEqual(['Facture1_01', 'Facture1_02', 'Facture1_03']);
    expect(service.currentInvoice()?.id).toBe('Facture1_01');
    expect(service.nbMasquees()).toBe(0);
  });

  it('keeps the current invoice on screen when it exceeds the new max, until decided', () => {
    http.expectOne('/api/factures').flush([resume('Facture1_01', 48), resume('Facture1_02', 8)]);
    http.expectOne('/api/factures/Facture1_01').flush(detail('Facture1_01', 48));
    http.expectOne('/api/factures/Facture1_02').flush(detail('Facture1_02'));

    service.setDifficulteMax(10);
    expect(service.queue().map(f => f.id)).toEqual(['Facture1_01', 'Facture1_02']); // 01 kept in place
    expect(service.currentInvoice()?.id).toBe('Facture1_01'); // kept, no extra GET
    http.expectNone('/api/factures/Facture1_01');

    service.validateCurrent();
    http.expectOne('/api/factures/Facture1_01/decision').flush(null, { status: 204, statusText: 'No Content' });
    expect(service.currentInvoice()?.id).toBe('Facture1_02'); // next eligible invoice
  });
});
