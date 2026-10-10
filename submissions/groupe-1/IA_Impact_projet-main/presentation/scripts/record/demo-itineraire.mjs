// Démo « itinéraire » : on tape Perpignan → Albi, on lance la recherche, la carte trace le trajet, on lit la frise.
import { record } from "./lib.mjs";

await record("itineraire", async ({ page, cam, click, type, wait, center, move }) => {
  await wait(800);
  const from = page.getByPlaceholder("Ville ou gare de départ");
  const f = await center(from);
  cam(2.1, f.x + 60, f.y + 60);
  await click(from, { ms: 1100 });
  await type("Perpignan");
  await page.keyboard.press("Escape");
  const to = page.getByPlaceholder("Ville ou gare d'arrivée");
  await click(to, { ms: 600 });
  await type("Albi");
  await page.keyboard.press("Escape");
  await wait(300);
  const btn = page.getByRole("button", { name: "Trouver mon trajet" });
  const b = await center(btn);
  cam(2.4, b.x, b.y);
  await click(btn, { ms: 700 });
  await wait(500);
  cam(1.05, 900, 420, 1.6);                    // recul : la carte trace le trajet
  await move(980, 470, 1400);
  await wait(2600);
  cam(1.7, 1000, 500, 1.4);                    // on suit la ligne vers la correspondance
  await move(820, 330, 1500);
  await wait(1600);
  cam(1.9, 180, 460, 1.4);                     // la frise du trajet à gauche
  await move(200, 470, 1100);
  await wait(900);
  await page.mouse.wheel(0, 260); await wait(900);
  await page.mouse.wheel(0, 260); await wait(1200);
  cam(1, 720, 405, 1.6);
  await move(1050, 380, 1200);
  await wait(1800);
});
