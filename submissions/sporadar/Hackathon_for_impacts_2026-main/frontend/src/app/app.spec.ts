import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { I18n } from './core/i18n/i18n';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('se crée et héberge le routeur', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('router-outlet')).not.toBeNull();
  });

  it("la langue de la page suit la bascule FR / EN", async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    expect(document.documentElement.lang).toBe('fr');

    TestBed.inject(I18n).lang.set('en');
    await fixture.whenStable();
    expect(document.documentElement.lang).toBe('en');
  });
});
