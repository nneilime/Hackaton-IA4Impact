import { Injectable, HostListener } from '@angular/core';
import { InvoiceService } from './invoice.service';

@Injectable({
  providedIn: 'root'
})
export class ShortcutService {
  constructor(private invoiceService: InvoiceService) {}

  // Cette fonction sera appelée par le composant principal
  handleKeyboardEvent(event: KeyboardEvent) {
    if (event.key === 'v' || event.key === 'V') {
      this.invoiceService.validateCurrent();
    } else if (event.key === 'r' || event.key === 'R') {
      this.invoiceService.rejectCurrent();
    }
  }
}
