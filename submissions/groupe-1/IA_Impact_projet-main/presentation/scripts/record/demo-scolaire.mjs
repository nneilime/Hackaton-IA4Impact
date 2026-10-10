// Démo « sortie scolaire » : formulaire de la classe, recherche, idées de sorties sur la carte et dans le bandeau.
import { record } from "./lib.mjs";

await record("scolaire", async ({ page, cam, click, type, wait, center, move }) => {
  const title = page.getByText("Préparer une sortie scolaire").first();
  const t = await center(title);
  cam(1.9, t.x + 60, t.y + 200, 1.4);
  await move(t.x, t.y + 40, 1100);
  await wait(800);
  const theme = page.locator("select").nth(2);
  await click(theme, { ms: 900 });
  await wait(500);
  const go = page.getByRole("button", { name: "Trouver des idées de sorties" });
  await go.scrollIntoViewIfNeeded();
  await wait(300);
  const g = await center(go);
  cam(2.3, g.x, g.y - 30, 1.3);
  await click(go, { ms: 1000 });
  await wait(900);
  cam(1.05, 900, 420, 1.6);                     // les idées apparaissent sur la carte
  await move(1000, 380, 1400);
  await wait(3000);
  cam(1.7, 1000, 650, 1.5);                     // et dans le bandeau du bas
  await move(900, 680, 1200);
  await wait(2500);
  await move(1250, 680, 1800);
  await wait(2200);
  cam(1, 720, 405, 1.5);
  await wait(2200);
});
