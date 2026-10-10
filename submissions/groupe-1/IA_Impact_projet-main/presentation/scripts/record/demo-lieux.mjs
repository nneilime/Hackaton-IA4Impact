// Démo « lieux » : onglet Lieux, Nîmes, les lieux à voir près de la gare, la fiche des Arènes, puis la 3D qu'on fait tourner.
import { record } from "./lib.mjs";

await record("lieux", async ({ page, cam, click, type, wait, center, move, drag }) => {
  const tab = page.getByRole("button", { name: "Lieux", exact: true }).or(page.getByRole("tab", { name: "Lieux" })).first();
  const tb = await center(tab);
  cam(2.2, tb.x + 120, tb.y + 80);
  await click(tab, { ms: 1100 });
  await wait(500);
  const filter = page.getByPlaceholder("Chercher une gare ou un département");
  await click(filter, { ms: 600 });
  await type("Nîmes");
  await wait(700);
  const st = page.locator("button.place-name", { hasText: "Nîmes Centre" }).first();
  const sc = await center(st);
  cam(1.8, sc.x + 200, sc.y + 120, 1.3);
  await click(st, { ms: 900 });
  await wait(1800);
  const card = page.locator("button.disc-card", { hasText: "Arènes de Nîmes" }).first();
  const cc = await center(card);
  cam(1.7, cc.x + 100, cc.y, 1.3);
  await click(card, { ms: 1000 });
  await wait(1500);
  cam(1.25, 720, 405, 1.4);                     // la fiche s'ouvre
  await move(760, 420, 1200);
  await wait(1500);
  const b3d = page.getByRole("button", { name: "Voir en 3D" });
  const bc = await center(b3d);
  cam(2.2, bc.x, bc.y, 1.2);
  await click(b3d, { ms: 900 });
  await wait(500);
  cam(1.6, 720, 330, 1.6);
  await wait(3500);                             // le modèle charge et tourne tout seul
  await move(640, 330, 900);
  await drag(380, 40, 2200);                    // on le fait tourner à la main
  await wait(700);
  await drag(-260, -60, 1800);
  await wait(2500);
  cam(1, 720, 405, 1.5);
  await wait(2000);
});
