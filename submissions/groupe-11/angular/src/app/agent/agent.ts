import { Component, ElementRef, HostListener, ViewChild, computed, effect, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { InvoiceService } from '../services/invoice.service';
import { ShortcutService } from '../services/shortcut.service';
import { Box, Check, Statut } from '../models/invoice.model';
import { Segment, diffSegments, listDiffSegments, montantEcart, trimLeadingZeros } from './diff';

const STATUT_LABEL: Record<Statut, string> = { OK: 'OK', KO: 'KO', A_VERIFIER: 'À vérifier' };

/** Margin added around each highlighted box, as a fraction of the scan width (~6 px on a 1190 px scan) */
const BOX_PADDING = 0.005;

/** Crops of the scan shown on each card: context kept around a box (fraction of the scan width), max zoom and size */
const CROP_MARGIN = 0.02;
const CROP_MAX_ZOOM = 1.5;
const CROP_MAX_WIDTH = 520;
const CROP_MAX_HEIGHT = 160;
const CROP_MAX = 4;

/** One crop, drawn with CSS background-position/size on the already loaded scan (no extra request) */
export interface Crop {
  width: number; height: number; backgroundSize: string; backgroundPosition: string;
  /** The cropped region in scan pixels, to draw it again larger when the agent clicks it */
  region: Box;
}

/** Largest zoom of a clicked crop (it also never exceeds 90 % of the window) */
const ZOOM_MAX_SCALE = 5;

/** CSS background geometry showing `region` of a scan at `scale` */
function cropAt(region: Box, largeur: number, hauteur: number, scale: number): Crop {
  const [x0, y0, x1, y1] = region;
  return {
    width: Math.round((x1 - x0) * scale),
    height: Math.round((y1 - y0) * scale),
    backgroundSize: `${Math.round(largeur * scale)}px ${Math.round(hauteur * scale)}px`,
    backgroundPosition: `${Math.round(-x0 * scale)}px ${Math.round(-y0 * scale)}px`,
    region,
  };
}

/**
 * Crops for a check's boxes ([x0, y0, x1, y1] in scan pixels), touching boxes merged, at most CROP_MAX.
 * Each box is first stretched to the printed `labels` on its row, left of it, so the crop shows which
 * field the value belongs to ("sous-total 4  50,48" rather than a bare "50,48").
 */
export function cropsFor(boxes: Box[], largeur: number, hauteur: number, labels: Box[] = [],
                         margin = CROP_MARGIN): Crop[] {
  const m = largeur * margin;
  const withLabel = boxes.map(b => labels
    .filter(l => l[1] < b[3] && b[1] < l[3] && l[2] <= b[0] + 2)  // same row, ends left of the value
    .reduce((u, l): Box => [Math.min(u[0], l[0]), Math.min(u[1], l[1]), Math.max(u[2], l[2]), Math.max(u[3], l[3])], b));
  return mergeTouching(withLabel.map(([x0, y0, x1, y1]): Box => [
    Math.max(0, x0 - m), Math.max(0, y0 - m / 2), Math.min(largeur, x1 + m), Math.min(hauteur, y1 + m / 2),
  ])).slice(0, CROP_MAX).map(region => {
    const [x0, y0, x1, y1] = region;
    return cropAt(region, largeur, hauteur, Math.min(CROP_MAX_ZOOM, CROP_MAX_WIDTH / (x1 - x0), CROP_MAX_HEIGHT / (y1 - y0)));
  });
}

/** Merge boxes that overlap (e.g. 'GHS' and '9606' read side by side), so no border crosses a neighbour's text */
export function mergeTouching(boxes: Box[]): Box[] {
  const out = boxes.map(b => [...b] as Box);
  for (let merged = true; merged;) {
    merged = false;
    for (let i = 0; i < out.length && !merged; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const [a, b] = [out[i], out[j]];
        if (a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3]) {
          out[i] = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])];
          out.splice(j, 1);
          merged = true;
          break;
        }
      }
    }
  }
  return out;
}

/** Checks whose `attendu` is a rule of the form or a total computed from the scan, not a value of the B2 file */
const RULE_CHECKS = new Set(['C1', 'C14', 'C15', 'C16', 'C17']);

/** `confiance`: OCR score, only on the side read from the scan (the B2 file and form rules are not OCR'd) */
interface Side { label: string; value: string; confiance?: number | null }

/**
 * A card's two values, with the characters that differ between them (null: nothing to highlight)
 * and, for amounts, the difference in euros (null if they are not amounts)
 */
export interface Comparison {
  reference: Side; suspect: Side;
  diff: { reference: Segment[]; suspect: Segment[] } | null;
  ecart: string | null;
}

/**
 * Checks whose two values are verdicts ("signature présente" / "signature absente", "fichier conforme" /
 * "Fichier B2 mal formé…"), not values read character by character: underlining the letters that differ
 * ("pré" / "ab") would suggest a misread where there is none.
 */
const NO_DIFF_CHECKS = new Set(['C0', 'C14', 'C16']);

/**
 * List checks (acts / prestations): under their message lines, the two lists are shown side by side with the
 * items present on one side only marked as a whole (a character diff would match 'PH7' against 'PH8')
 */
const LIST_DIFF_CHECKS = new Set(['C7', 'C9', 'C10b', 'C11']);

/**
 * Which side's extra items each list check really verifies ([scan, B2 file]): C7 / C9 require the scan's items
 * to be in the file, C10b the file's items to be on the scan, C11 both. The other side is shown unmarked.
 */
const LIST_DIFF_MARKS: Record<string, [boolean, boolean]> = {
  C7: [true, false], C9: [true, false], C10b: [false, true], C11: [true, true],
};

/** Signature zones: extract.py already makes their boxes generous (stamps overflow), so only a thin crop margin */
const SIGNATURE_CHECKS = new Set(['C14', 'C16']);
const SIGNATURE_CROP_MARGIN = 0.008;

/** Money checks fed by the scan's sub-totals: when C15 (scan total = 1+2+3 + 4) is OK, the scan is self-consistent */
const SUBTOTAL_CHECKS = new Set(['C10', 'C13']);

@Component({
  selector: 'app-agent',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './agent.html',
  styleUrl: './agent.css',
})
export class AgentComponent {
  private invoiceService = inject(InvoiceService);
  private shortcutService = inject(ShortcutService);

  isDarkMode = signal<boolean>(true);

  currentInvoice = this.invoiceService.currentInvoice;
  isFinished = this.invoiceService.isFinished;
  loading = this.invoiceService.loading;
  saving = this.invoiceService.saving;
  error = this.invoiceService.error;
  position = computed(() => this.invoiceService.currentInvoiceIndex() + 1);
  total = computed(() => this.invoiceService.queue().length);
  difficulteMax = this.invoiceService.difficulteMax;
  nbMasquees = this.invoiceService.nbMasquees;

  /** Couleur du badge de difficulté : vert ≤ 20, ambre ≤ 60, rouge au-delà (le texte porte toujours l'info) */
  classeDifficulte = computed(() => {
    const d = this.currentInvoice()?.difficulte ?? 100;
    if (d <= 20) return 'badge-difficulte-basse';
    if (d <= 60) return 'badge-difficulte-moyenne';
    return 'badge-difficulte-haute';
  });

  @ViewChild('scrollPort') scrollPort?: ElementRef<HTMLElement>;

  constructor() {
    // Recentrage vertical sur la première anomalie à chaque changement de facture.
    // L'image peut être en cache (pas d'événement load) : ce recentrage couvre ce cas,
    // onImageLoad() couvre le chargement différé.
    effect(() => {
      this.currentInvoice()?.id;
      this.selectedCode.set(null);  // a new invoice starts with no card selected
      this.zoomedCrop.set(null);
      requestAnimationFrame(() => this.centerOnFirstBox(true));
    });
  }

  /** C0 KO: the B2 file is malformed (columns shifted), so every check that uses its values is meaningless */
  b2Broken = computed(() =>
    (this.currentInvoice()?.checks ?? []).some(c => c.code === 'C0' && c.statut === 'KO'));

  /** Contrôles à montrer à l'agent : KO d'abord, puis À vérifier. B2 mal formé : C0 seul. */
  anomalies = computed(() =>
    (this.currentInvoice()?.checks ?? [])
      .filter(c => c.statut !== 'OK' && (!this.b2Broken() || c.code === 'C0'))
      .sort((a, b) => (a.statut === b.statut ? 0 : a.statut === 'KO' ? -1 : 1))
  );

  /**
   * The scan's sub-totals add up to its printed total (C15 OK). On a sub-total card (C10, C13) this hints that
   * the difference comes from the B2 file rather than from a misread of the scan.
   */
  scanCoherent = computed(() => (this.currentInvoice()?.checks ?? []).some(c => c.code === 'C15' && c.statut === 'OK'));
  isSubtotalCheck(c: Check) { return SUBTOTAL_CHECKS.has(c.code); }


  /** Crop the agent clicked, shown large over the page (click or Échap closes it) */
  zoomedCrop = signal<Crop | null>(null);

  openZoom(crop: Crop) {
    const inv = this.currentInvoice();
    if (!inv) return;
    const [x0, y0, x1, y1] = crop.region;
    const scale = Math.min(ZOOM_MAX_SCALE, (window.innerWidth * 0.9) / (x1 - x0), (window.innerHeight * 0.85) / (y1 - y0));
    this.zoomedCrop.set(cropAt(crop.region, inv.image.largeur, inv.image.hauteur, scale));
  }

  closeZoom() { this.zoomedCrop.set(null); }

  /** Card the agent clicked: the scan is centred on its boxes and the other boxes fade out */
  selectedCode = signal<string | null>(null);

  select(code: string) {
    this.selectedCode.set(code);
    requestAnimationFrame(() => this.centerOn(this.highlights().find(h => h.code === code)));
  }

  /** Checks hidden because the B2 file is malformed */
  nbNonEvalues = computed(() =>
    this.b2Broken() ? (this.currentInvoice()?.checks ?? []).filter(c => c.code !== 'C0').length : 0);
  nbKo = computed(() => this.anomalies().filter(c => c.statut === 'KO').length);
  nbAVerifier = computed(() => this.anomalies().length - this.nbKo());

  /** Cadres des anomalies, convertis des pixels de l'image d'origine en % de l'image affichée */
  /** Scan crops of each card, so the agent checks the pixels right next to the two values */
  crops = computed(() => {
    const inv = this.currentInvoice();
    if (!inv) return new Map<string, Crop[]>();
    return new Map(this.anomalies().map(c =>
      [c.code, cropsFor(c.boxes, inv.image.largeur, inv.image.hauteur, c.contexte ?? [],
                        SIGNATURE_CHECKS.has(c.code) ? SIGNATURE_CROP_MARGIN : CROP_MARGIN)]));
  });

  highlights = computed(() => {
    const inv = this.currentInvoice();
    if (!inv) return [];
    const { largeur, hauteur } = inv.image;
    // OCR boxes hug the glyphs: widen them so the border never covers a character
    const pad = largeur * BOX_PADDING;
    return this.anomalies().flatMap(c =>
      mergeTouching(c.boxes.map(([x0, y0, x1, y1]: Box): Box => [
        Math.max(0, x0 - pad), Math.max(0, y0 - pad), Math.min(largeur, x1 + pad), Math.min(hauteur, y1 + pad),
      ])).map(([l, t, r, b]) => ({
        code: c.code,
        statut: c.statut,
        left: (l / largeur) * 100,
        top: (t / hauteur) * 100,
        width: ((r - l) / largeur) * 100,
        height: ((b - t) / hauteur) * 100,
      }))
    );
  });

  statutLabel(c: Check) { return STATUT_LABEL[c.statut]; }

  /**
   * Left (black) = what was read: the scan, or the B2 file itself for C0.
   * Right (red / amber) = what it is compared with: the B2 value, or the form rule for C0, C1 and C14–C17.
   */
  comparison(c: Check): Comparison {
    const sides: { reference: Side; suspect: Side } = {
      reference: c.code === 'C0' ? { label: 'Fichier B2 (constaté)', value: c.lu }
        : { label: "Image (lu par l'IA)", value: c.lu, confiance: c.confiance },
      suspect: {
        label: c.code === 'C0' ? 'Attendu' : RULE_CHECKS.has(c.code) ? 'Attendu (règle du formulaire)' : 'Fichier B2 (facture)',
        value: c.attendu,
      },
    };
    [sides.reference.value, sides.suspect.value] = trimLeadingZeros(sides.reference.value, sides.suspect.value);
    return {
      ...sides,
      diff: NO_DIFF_CHECKS.has(c.code) ? null
        : LIST_DIFF_CHECKS.has(c.code) ? listDiffSegments(sides.reference.value, sides.suspect.value, ...LIST_DIFF_MARKS[c.code])
        : diffSegments(sides.reference.value, sides.suspect.value),
      ecart: montantEcart(sides.reference.value, sides.suspect.value),
    };
  }

  /** OCR confidence as a percentage, rounded down: 0.999 shows 99 %, only a perfect read shows 100 % */
  confiancePct(c: number) { return Math.floor(c * 100); }

  /** Comparisons of the current invoice's cards, computed once per invoice rather than on every change detection */
  comparisons = computed(() => new Map(this.anomalies().map(c => [c.code, this.comparison(c)])));

  toggleTheme() {
    this.isDarkMode.update(val => !val);
  }

  /** Recentrage vertical du scroll sur la première boîte rouge (KO d'abord, sinon À vérifier). */
  centerOnFirstBox(resetWhenEmpty = false): void {
    const el = this.scrollPort?.nativeElement;
    if (!el) return;
    const box = this.highlights()[0];
    if (!box) {
      if (resetWhenEmpty) el.scrollTop = 0;
      return;
    }
    this.centerOn(box);
  }

  /** Scrolls the scan so that a highlighted box sits in the middle of the viewer */
  private centerOn(box?: { top: number; height: number }): void {
    const el = this.scrollPort?.nativeElement;
    if (!el || !box) return;
    const centerY = ((box.top + box.height / 2) / 100) * el.scrollHeight;
    el.scrollTop = Math.max(0, centerY - el.clientHeight / 2);
  }

  onImageLoad(): void {
    requestAnimationFrame(() => this.centerOnFirstBox(false));
  }

  /** Défilement vertical au clavier (pas de scroll horizontal par design). */
  private panViewer(event: KeyboardEvent): boolean {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return false;
    const el = this.scrollPort?.nativeElement;
    if (!el) return false;
    event.preventDefault();
    const step = event.shiftKey ? 320 : 120;
    el.scrollBy({ top: event.key === 'ArrowDown' ? step : -step, behavior: 'smooth' });
    return true;
  }

  private isTypingTarget(event: KeyboardEvent): boolean {
    const t = event.target as HTMLElement | null;
    return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
  }

  @HostListener('window:keydown', ['$event'])
  handleKeyDown(event: KeyboardEvent) {
    if (this.zoomedCrop()) {  // a zoomed crop is open: Échap closes it, nothing else reaches the page
      if (event.key === 'Escape') this.closeZoom();
      return;
    }
    if (this.isFinished() || this.isTypingTarget(event)) return;
    if (this.panViewer(event)) return;
    this.shortcutService.handleKeyboardEvent(event);
  }

  validate() { this.invoiceService.validateCurrent(); }
  reject() { this.invoiceService.rejectCurrent(); }
  retry() { this.invoiceService.load(); }
  setDifficulteMax(v: number) { this.invoiceService.setDifficulteMax(v); }
  resetDifficulteMax() { this.invoiceService.resetDifficulteMax(); }
}
