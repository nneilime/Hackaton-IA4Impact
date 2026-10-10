// Démo « simulation » : trajet Perpignan → Albi déjà cherché, on lance la simulation, on accélère,
// la caméra suit le train puis descend sur les hublots où défile le paysage.
import { record } from "./lib.mjs";
import fs from "node:fs";

// Les photos des hublots se chargent à la demande : on les met en cache avant de filmer, sinon des fenêtres restent vides
const pub = new URL("../../../frontend/public/", import.meta.url);
const imgs = ["scenery", "discoveries"].flatMap((d) => fs.readdirSync(new URL(d + "/", pub)).map((f) => `/${d}/${f}`));

await record("simulation", async ({ page, cam, click, type, wait, center, move }) => {
  await page.evaluate((list) => Promise.all(list.map((u) => new Promise((ok) => { const i = new Image(); i.onload = i.onerror = ok; i.src = u; }))), imgs);
  // Mise en place hors champ caméra (zoom serré sur la carte pendant la recherche)
  await page.getByPlaceholder("Ville ou gare de départ").fill("Perpignan");
  await page.getByPlaceholder("Ville ou gare d'arrivée").fill("Albi");
  await page.getByRole("button", { name: "Trouver mon trajet" }).click();
  await wait(2500);
  const sim = page.getByRole("button", { name: "Simuler le trajet" }).first();
  await sim.scrollIntoViewIfNeeded();
  await wait(400);
  const s = await center(sim);
  cam(2.2, s.x, s.y - 40);
  await click(sim, { ms: 1200 });
  await wait(700);
  cam(1.6, 1000, 260, 1.8);                     // le train 3D démarre sur la carte
  await move(1150, 300, 1500);
  await wait(3000);
  const x2 = page.locator(".sim-speed button", { hasText: "×2" });
  const v = await center(x2);
  cam(2.6, v.x - 60, v.y, 1.2);
  await click(x2, { ms: 1000 });
  await wait(600);
  cam(1.5, 1000, 280, 1.4);
  await wait(3200);
  cam(1.8, 640, 650, 1.6);                      // descente sur les hublots du carrousel
  await move(560, 660, 1300);
  await wait(3000);
  cam(1.8, 1150, 650, 2.2);                     // travelling le long des fenêtres
  await move(1180, 660, 2000);
  await wait(3500);
  cam(1, 720, 405, 1.6);
  await move(1000, 300, 1200);
  await wait(3000);
});
