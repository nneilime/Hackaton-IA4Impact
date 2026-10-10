import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { switchMap, takeWhile, tap } from 'rxjs/operators';
import { StatsService } from '../services/stats.service';
import {
  DashboardStats, EtablissementStats,
  CheckRepartition, CategoryRepartition, OcrStatus, OcrFactureStatus
} from '../models/stats.model';

const OCR_POLL_MS = 3000;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  private statsService = inject(StatsService);
  private ocrSub: Subscription | null = null;

  stats       = signal<DashboardStats | null>(null);
  ocr         = signal<OcrStatus | null>(null);
  loading     = signal(true);
  error       = signal<string | null>(null);
  ocrPolling  = signal(false);   // true while auto-refresh is running

  // OCR panel state
  ocrExpanded   = signal(false);
  ocrSearchTerm = signal('');

  ngOnInit() {
    this.statsService.getStats().subscribe({
      next: (data) => { this.stats.set(data); this.loading.set(false); },
      error: () => {
        this.error.set('Impossible de charger les statistiques. Vérifiez que le backend est démarré.');
        this.loading.set(false);
      },
    });

    // Initial fetch + poll every OCR_POLL_MS until nb_traites === nb_total.
    // We start with an immediate fetch (startWith(0) trick via the interval),
    // so the data appears instantly and then refreshes on the timer.
    this.ocrSub = interval(OCR_POLL_MS).pipe(
      // Kick off immediately before the first interval tick
      switchMap(() => this.statsService.getOcrStatus()),
      tap(data => {
        this.ocr.set(data);
        this.ocrPolling.set(data.nb_traites < data.nb_total);
      }),
      // inclusive=true: the last emission (complete state) still updates the view
      takeWhile(data => data.nb_traites < data.nb_total, /* inclusive= */ true),
    ).subscribe({
      complete: () => this.ocrPolling.set(false),
    });

    // Fire the very first fetch immediately (don't wait for the first interval tick)
    this.statsService.getOcrStatus().subscribe(data => {
      this.ocr.set(data);
      this.ocrPolling.set(data.nb_traites < data.nb_total);
    });
  }

  ngOnDestroy() {
    this.ocrSub?.unsubscribe();
  }

  // ── Formatting helpers ──────────────────────────────────────────────────

  fmt(v: number): string {
    return v.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '\u00a0€';
  }

  pct(v: number, decimals = 0): string {
    return (v * 100).toFixed(decimals) + '%';
  }

  // ── Donut chart ──────────────────────────────────────────────────────────
  donutSegments(ko: number, av: number, total: number): { d: string; color: string; label: string; value: number }[] {
    if (total === 0) return [];
    const conformes = total - ko - av;
    const slices = [
      { value: ko,        color: '#fb7185', label: 'KO' },
      { value: av,        color: '#fbbf24', label: 'À vérifier' },
      { value: conformes, color: '#34d399', label: 'Conformes' },
    ].filter(s => s.value > 0);

    const cx = 60, cy = 60, r = 52, inner = 32;
    let startAngle = -Math.PI / 2;
    return slices.map(s => {
      const angle = (s.value / total) * 2 * Math.PI;
      const endAngle = startAngle + angle;
      const large = angle > Math.PI ? 1 : 0;
      const x1 = cx + r * Math.cos(startAngle), y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle),   y2 = cy + r * Math.sin(endAngle);
      const ix1 = cx + inner * Math.cos(startAngle), iy1 = cy + inner * Math.sin(startAngle);
      const ix2 = cx + inner * Math.cos(endAngle),   iy2 = cy + inner * Math.sin(endAngle);
      const d = `M${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} L${ix2},${iy2} A${inner},${inner} 0 ${large},0 ${ix1},${iy1} Z`;
      startAngle = endAngle;
      return { d, color: s.color, label: s.label, value: s.value };
    });
  }

  // ── Category breakdown ───────────────────────────────────────────────────
  maxCategoryKo(cats: CategoryRepartition[]): number {
    return Math.max(1, ...cats.map(c => c.nb_invoices_ko));
  }

  // ── Fraud score colour ───────────────────────────────────────────────────
  scoreClass(score: number): string {
    if (score >= 70) return 'danger';
    if (score >= 40) return 'warning';
    return 'success';
  }

  // ── Check bar chart ──────────────────────────────────────────────────────
  activeChecks(checks: CheckRepartition[]): CheckRepartition[] {
    return checks.filter(c => c.nb_ko > 0 || c.nb_a_verifier > 0);
  }

  activeChecksSorted(checks: CheckRepartition[]): CheckRepartition[] {
    return this.activeChecks(checks).sort((a, b) => b.nb_ko - a.nb_ko);
  }

  maxCheckCount(checks: CheckRepartition[]): number {
    return Math.max(1, ...checks.map(c => c.nb_ko + c.nb_a_verifier));
  }

  barWidthPct(value: number, max: number): number {
    return Math.round((value / max) * 100);
  }

  // ── Etablissements ───────────────────────────────────────────────────────
  maxKo(etablissements: EtablissementStats[]): number {
    return Math.max(1, ...etablissements.map(e => e.nb_ko));
  }

  diffClass(niveau: string | null | undefined): string {
    switch (niveau) {
      case 'Facile':          return 'diff-facile';
      case 'Modérée':         return 'diff-moderee';
      case 'Moyenne':         return 'diff-moyenne';
      case 'Difficile':       return 'diff-difficile';
      case 'Très difficile':  return 'diff-tres-difficile';
      default:                return '';
    }
  }

  // ── OCR status helpers ────────────────────────────────────────────────────
  toggleOcrExpanded() { this.ocrExpanded.update(v => !v); }

  filteredOcrRows(factures: OcrFactureStatus[]): OcrFactureStatus[] {
    const term = this.ocrSearchTerm().toLowerCase();
    return term ? factures.filter(f => f.id.toLowerCase().includes(term)) : factures;
  }

  ocrProgressPct(o: OcrStatus): number {
    return o.nb_total > 0 ? Math.round((o.nb_traites / o.nb_total) * 100) : 0;
  }

  minZoneScore(scores: Record<string, number> | null): number | null {
    if (!scores) return null;
    const vals = Object.values(scores);
    return vals.length ? Math.min(...vals) : null;
  }

  scoreColor(score: number): string {
    if (score >= 0.9) return '#34d399';
    if (score >= 0.8) return '#fbbf24';
    return '#fb7185';
  }

  zoneLabel(zone: string): string {
    const LABELS: Record<string, string> = {
      '1': 'Cerfa', '2': 'FINESS', '3': 'Lot', '4': 'Facture', '5': 'Assuré',
      '6': 'Zone 6', '7': 'Zone 7', '8': 'Ss-total 1+2+3',
      '9': 'Exécutants', '10': 'Actes', '11': 'Signatures', '12': 'Ss-total 4',
      '13': 'Total', '14': 'Sign. directeur', '15': 'Code Cerfa',
    };
    return LABELS[zone] ?? `Zone ${zone}`;
  }

  sortedZones(scores: Record<string, number>): string[] {
    return Object.keys(scores).sort((a, b) => parseInt(a) - parseInt(b));
  }

  countWithUnreadable(factures: OcrFactureStatus[]): number {
    return factures.filter(f => f.traite && f.zones_illisibles.length > 0).length;
  }
}
