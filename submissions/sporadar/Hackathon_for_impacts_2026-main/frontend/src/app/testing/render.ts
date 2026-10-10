import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideIcons } from '@ng-icons/core';
import * as lucide from '@ng-icons/lucide';
import { I18n } from '../core/i18n/i18n';

/** Tous les pictogrammes lucide, pour que les gabarits se rendent comme dans l'application. */
const ICONS = Object.fromEntries(Object.entries(lucide).filter(([name]) => name.startsWith('lucide')));

/** Monte un composant avec ses entrées signal, sans réseau réel (HttpTestingController). */
export async function render<T>(
  component: Type<T>,
  inputs: Record<string, unknown> = {},
  lang: 'fr' | 'en' = 'fr',
): Promise<{ fixture: ComponentFixture<T>; element: HTMLElement; http: HttpTestingController }> {
  TestBed.configureTestingModule({
    imports: [component],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), provideIcons(ICONS)],
  });
  TestBed.inject(I18n).lang.set(lang);
  const fixture = TestBed.createComponent(component);
  for (const [name, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(name, value);
  }
  await fixture.whenStable();
  return { fixture, element: fixture.nativeElement as HTMLElement, http: TestBed.inject(HttpTestingController) };
}

/** Texte visible d'un élément, espaces normalisés. */
export function textOf(element: Element): string {
  return (element.textContent ?? '').replace(/\s+/g, ' ').trim();
}
