// SPDX-License-Identifier: AGPL-3.0-or-later
// Présentation Pecha Kucha 20×20 : 20 diapositives de 20 secondes, un visuel animé par diapositive (p5.js),
// quelques mots, une voix facultative. Tous les chiffres viennent de window.VEILLE (vraies exécutions).
(function () {
  const L = window.VEILLE;
  if (!L || !window.p5) return;

  const SLIDE_SECONDS = 20;
  const COLOR = {
    background: [11, 17, 23], card: [24, 34, 47], line: [60, 74, 92], text: [241, 242, 246], dim: [140, 152, 168],
    green: [46, 213, 115], blue: [74, 163, 255], amber: [255, 176, 46], red: [255, 90, 104],
  };

  // ── Petits outils de dessin (p5.js en mode « instance ») ───────────────────

  const ease = x => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
  const reveal = (t, start, duration = 0.8) => ease((t - start) / duration);
  const frNumber = (n, digits = 0) => Number(n).toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits });

  function fillColor(p, color, alpha = 255) { p.fill(color[0], color[1], color[2], alpha); }
  function strokeColor(p, color, alpha = 255) { p.stroke(color[0], color[1], color[2], alpha); }

  function drawText(p, content, x, y, size, color = COLOR.text, align = 'center', weight = 'normal') {
    p.noStroke(); fillColor(p, color);
    p.textStyle(weight === 'bold' ? p.BOLD : p.NORMAL);
    p.textSize(size);
    p.textAlign(align === 'left' ? p.LEFT : align === 'right' ? p.RIGHT : p.CENTER, p.CENTER);
    p.text(content, x, y);
  }

  function drawCard(p, x, y, w, h, borderColor = COLOR.line, alpha = 255) {
    fillColor(p, COLOR.card, alpha); strokeColor(p, borderColor, alpha); p.strokeWeight(2); p.rect(x, y, w, h, 14);
  }

  function arrowBetween(p, x1, y1, x2, y2, color, size = 9) {
    strokeColor(p, color); fillColor(p, color); p.strokeWeight(2); p.line(x1, y1, x2, y2);
    const angle = Math.atan2(y2 - y1, x2 - x1);
    p.push(); p.translate(x2, y2); p.rotate(angle); p.noStroke(); p.triangle(0, 0, -size, size * 0.55, -size, -size * 0.55); p.pop();
  }

  // Zone de dessin : on laisse de la place au titre (en haut) et à la barre de lecture (en bas).
  function drawingArea(p) { return { x: p.width * 0.06, y: p.height * 0.215, w: p.width * 0.88, h: p.height * 0.55 }; }
  const unit = p => Math.min(p.width, p.height) / 700;

  // Crée un sketch p5 : `build` reçoit p et un chronomètre (secondes écoulées depuis le début de la diapositive).
  function sketchOf(build) {
    return function (p) {
      const startedAt = performance.now();
      const clock = () => (performance.now() - startedAt) / 1000;
      p.setup = () => { p.createCanvas(host.clientWidth, host.clientHeight); p.frameRate(30); p.textFont('Plus Jakarta Sans'); };
      build(p, clock);
    };
  }

  // ── Les 20 visuels ─────────────────────────────────────────────────────────

  function visualTitle(p, clock) {
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p), cy = area.y + area.h * 0.45;
      p.background(COLOR.background);
      const leftX = p.width * 0.28, rightX = p.width * 0.72;
      // l'IA (cercle) propose : une particule voyage jusqu'au code (carré) qui décide
      fillColor(p, COLOR.blue, 40 + 30 * Math.sin(t * 3)); p.noStroke(); p.circle(leftX, cy, 190 * u);
      strokeColor(p, COLOR.blue); p.strokeWeight(4); p.noFill(); p.circle(leftX, cy, 150 * u);
      fillColor(p, COLOR.green, 30); p.noStroke(); p.rectMode(p.CENTER); p.rect(rightX, cy, 170 * u, 170 * u, 18);
      strokeColor(p, COLOR.green); p.strokeWeight(4); p.noFill(); p.rect(rightX, cy, 140 * u, 140 * u, 14); p.rectMode(p.CORNER);
      const travel = (t % 2.4) / 2.4, x = p.lerp(leftX + 80 * u, rightX - 80 * u, ease(travel));
      fillColor(p, COLOR.amber); p.noStroke(); p.circle(x, cy + Math.sin(travel * Math.PI) * -40 * u, 20 * u);
      if (travel > 0.95) { fillColor(p, COLOR.green, 120); p.rectMode(p.CENTER); p.rect(rightX, cy, 190 * u, 190 * u, 22); p.rectMode(p.CORNER); }
      drawText(p, 'propose', leftX, cy + 140 * u, 34 * u, COLOR.blue, 'center', 'bold');
      drawText(p, 'décide', rightX, cy + 140 * u, 34 * u, COLOR.green, 'center', 'bold');
      drawText(p, 'Lallemand Plant Care · Hackathon IA for Impact 2026', p.width / 2, area.y + area.h * 1.02, 20 * u, COLOR.dim);
    };
  }

  function visualDispersion(p, clock) {
    const formats = ['PDF', 'CSV', 'XLSX', 'HTML', 'XML', 'JSON'], countries = ['FR', 'CA', 'US', 'BR', 'MX', 'UY', 'DE', 'ES', 'IT'];
    const documents = Array.from({ length: 46 }, (_, i) => ({
      seed: i * 7.31, label: i % 3 === 0 ? countries[i % countries.length] : formats[i % formats.length],
      color: [COLOR.blue, COLOR.amber, COLOR.green, COLOR.red][i % 4], size: 60 + (i * 13) % 50,
    }));
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      documents.forEach(doc => {
        const spread = value => Math.min(1, Math.max(0, (value - 0.2) / 0.6)), x = area.x + spread(p.noise(doc.seed, t * 0.12)) * area.w * 0.92, y = area.y + spread(p.noise(doc.seed + 50, t * 0.12)) * area.h * 0.85;
        p.push(); p.translate(x, y); p.rotate((p.noise(doc.seed + 99, t * 0.1) - 0.5) * 1.2);
        fillColor(p, doc.color, 50); strokeColor(p, doc.color, 200); p.strokeWeight(2);
        p.rect(0, 0, doc.size * u * 0.8, doc.size * u, 6);
        drawText(p, doc.label, doc.size * u * 0.4, doc.size * u * 0.5, 15 * u, COLOR.text, 'center', 'bold');
        p.pop();
      });
      const swing = reveal(t, 2.5, 1.2);
      drawText(p, 'dizaines de bases · formats · langues', p.width / 2, area.y + area.h * 1.03, 30 * u, COLOR.text, 'center', 'bold');
      fillColor(p, COLOR.background, 140 * swing); p.noStroke(); p.rect(0, area.y + area.h * 0.96, p.width, 60 * u);
      drawText(p, 'dizaines de bases · formats · langues', p.width / 2, area.y + area.h * 1.03, 30 * u, COLOR.text, 'center', 'bold');
    };
  }

  function visualThreeBricks(p, clock) {
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const columns = [
        { x: p.width * 0.2, title: 'IA locale', subtitle: 'RTX 3090 de la constellation', color: COLOR.blue, start: 0.5 },
        { x: p.width * 0.5, title: 'Qdrant', subtitle: 'mémoire vectorielle', color: COLOR.amber, start: 2.5 },
        { x: p.width * 0.8, title: 'Pydantic', subtitle: 'contrat de données', color: COLOR.green, start: 4.5 },
      ];
      columns.forEach((c, i) => {
        const shown = reveal(t, c.start), cy = area.y + area.h * 0.42;
        p.push(); p.translate(c.x, cy + (1 - shown) * 40);
        strokeColor(p, c.color, 255 * shown); fillColor(p, c.color, 40 * shown); p.strokeWeight(4);
        if (i === 0) {                               // puce
          p.rectMode(p.CENTER); p.rect(0, 0, 130 * u, 130 * u, 14); p.rect(0, 0, 70 * u, 70 * u, 8);
          for (let k = -2; k <= 2; k++) { p.line(k * 26 * u, -65 * u, k * 26 * u, -90 * u); p.line(k * 26 * u, 65 * u, k * 26 * u, 90 * u); }
          p.rectMode(p.CORNER);
        } else if (i === 1) {                        // pile de disques (base de données)
          for (let k = 0; k < 3; k++) { p.ellipse(0, (k - 1) * 46 * u, 150 * u, 50 * u); p.line(-75 * u, (k - 1) * 46 * u, -75 * u, (k - 1) * 46 * u + 46 * u); p.line(75 * u, (k - 1) * 46 * u, 75 * u, (k - 1) * 46 * u + 46 * u); }
        } else {                                     // bouclier avec coche
          p.beginShape(); p.vertex(0, -80 * u); p.vertex(70 * u, -50 * u); p.vertex(60 * u, 40 * u); p.vertex(0, 85 * u); p.vertex(-60 * u, 40 * u); p.vertex(-70 * u, -50 * u); p.endShape(p.CLOSE);
          p.noFill(); p.strokeWeight(7); p.line(-30 * u, 5 * u, -8 * u, 30 * u); p.line(-8 * u, 30 * u, 36 * u, -25 * u);
        }
        p.pop();
        drawText(p, c.title, c.x, cy + 135 * u, 34 * u, [c.color[0], c.color[1], c.color[2]], 'center', 'bold');
        fillColor(p, COLOR.dim, 255 * shown); drawText(p, c.subtitle, c.x, cy + 175 * u, 20 * u, COLOR.dim);
      });
    };
  }

  function visualChain(p, clock) {
    const performance_ = L.performance, total = performance_.passages;
    const share = { pass: performance_.first_try / total, retry: performance_.rescued_by_retry / total };
    const labels = ['Sources', 'Qdrant', 'IA locale', 'Pydantic', 'Preuve', 'Publié'];
    let particles = [], published = 0, expert = 0, lastSpawn = 0;
    const node = (area, i) => ({ x: area.x + area.w * (0.05 + 0.9 * i / 5), y: area.y + area.h * 0.28 });
    const expertNode = area => ({ x: area.x + area.w * 0.7, y: area.y + area.h * 0.76 });

    function planRoute(area) {
      const n = i => node(area, i), dip = (from, to) => ({ x: (n(from).x + n(to).x) / 2, y: n(from).y + area.h * 0.24 });
      const roll = Math.random();
      if (roll < share.pass) return { points: [0, 1, 2, 3, 4, 5].map(n), kind: 'pass' };
      if (roll < share.pass + share.retry) return { points: [n(0), n(1), n(2), n(3), dip(3, 2), n(2), n(3), n(4), n(5)], kind: 'retry' };
      return { points: [n(0), n(1), n(2), n(3), dip(3, 2), n(2), n(3), dip(3, 2), n(2), n(3), expertNode(area)], kind: 'expert' };
    }

    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      labels.forEach((name, i) => {
        const pos = node(area, i), color = i === 2 ? COLOR.blue : i >= 3 ? COLOR.green : COLOR.dim;
        drawCard(p, pos.x - 52 * u, pos.y - 28 * u, 104 * u, 56 * u, color);
        drawText(p, name, pos.x, pos.y, 17 * u, COLOR.text, 'center', 'bold');
        if (i < 5) { const next = node(area, i + 1); arrowBetween(p, pos.x + 56 * u, pos.y, next.x - 58 * u, next.y, COLOR.line, 7 * u); }
      });
      const ex = expertNode(area);
      drawCard(p, ex.x - 70 * u, ex.y - 26 * u, 140 * u, 52 * u, COLOR.amber);
      drawText(p, 'Expert humain', ex.x, ex.y, 17 * u, COLOR.amber, 'center', 'bold');

      if (t - lastSpawn > 0.42 && particles.length < 60) {
        lastSpawn = t; const route = planRoute(area);
        particles.push({ ...route, index: 1, x: route.points[0].x, y: route.points[0].y, color: COLOR.blue, failed: 0 });
      }
      particles = particles.filter(particle => {
        const target = particle.points[particle.index];
        const dx = target.x - particle.x, dy = target.y - particle.y, distance = Math.hypot(dx, dy), step = 5.2 * u;
        if (distance < step) {
          particle.x = target.x; particle.y = target.y; particle.index++;
          const isDip = particle.points[particle.index - 1].y > node(area, 0).y + area.h * 0.1 && particle.index - 1 < particle.points.length - 1;
          if (isDip) { particle.failed++; particle.color = particle.kind === 'expert' && particle.failed >= 2 ? COLOR.red : COLOR.amber; }
          if (particle.index >= particle.points.length) {
            if (particle.kind === 'expert') expert++; else published++;
            return false;
          }
        } else { particle.x += dx / distance * step; particle.y += dy / distance * step; }
        if (particle.kind === 'pass' && particle.index > 3) particle.color = COLOR.green;
        if (particle.kind === 'retry' && particle.index > 6) particle.color = COLOR.green;
        if (particle.kind === 'expert' && particle.index === particle.points.length - 1) particle.color = COLOR.red;
        fillColor(p, particle.color); p.noStroke(); p.circle(particle.x, particle.y, 14 * u);
        return true;
      });
      drawText(p, `publiés ${published}`, area.x + area.w * 0.18, area.y + area.h * 0.72, 30 * u, COLOR.green, 'center', 'bold');
      drawText(p, `vers l'expert ${expert}`, area.x + area.w * 0.18, area.y + area.h * 0.88, 24 * u, COLOR.red, 'center', 'bold');
    };
  }

  function visualSources(p, clock) {
    const groups = [
      { name: 'Europe', x: 0.27, items: [{ name: 'e-Phy · France', note: 'CSV · français', color: COLOR.blue }] },
      { name: 'Amérique du Nord', x: 0.73, items: [{ name: 'PMRA · Canada', note: 'API ouverte · anglais', color: COLOR.amber }, { name: 'EPA · États-Unis', note: 'XLSX + PDF · anglais', color: COLOR.green }] },
    ];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const sinkX = p.width / 2, sinkY = area.y + area.h * 0.9;
      groups.forEach((group, g) => {
        const gx = p.width * group.x, shown = reveal(t, 0.4 + g * 1.2);
        strokeColor(p, COLOR.line, 200 * shown); p.noFill(); p.strokeWeight(2); p.ellipse(gx, area.y + area.h * 0.34, p.width * 0.4, area.h * 0.66);
        drawText(p, group.name.toUpperCase(), gx, area.y + area.h * 0.06, 20 * u, COLOR.dim, 'center', 'bold');
        group.items.forEach((item, i) => {
          const y = area.y + area.h * (group.items.length === 1 ? 0.34 : 0.24 + i * 0.22);
          drawCard(p, gx - 140 * u, y - 36 * u, 280 * u, 72 * u, item.color, 255 * shown);
          drawText(p, item.name, gx, y - 10 * u, 22 * u, COLOR.text, 'center', 'bold');
          drawText(p, item.note, gx, y + 17 * u, 16 * u, COLOR.dim);
          for (let k = 0; k < 4; k++) {            // flux de données vers le modèle commun
            const phase = ((t * 0.5 + k / 4 + i * 0.1) % 1), x = p.lerp(gx, sinkX, ease(phase)), yy = p.lerp(y + 40 * u, sinkY - 30 * u, ease(phase));
            fillColor(p, item.color, 220 * shown); p.noStroke(); p.circle(x, yy, 9 * u);
          }
        });
      });
      const sinkShown = reveal(t, 3);
      drawCard(p, sinkX - 190 * u, sinkY - 30 * u, 380 * u, 60 * u, COLOR.green, 255 * sinkShown);
      drawText(p, 'un seul modèle de données', sinkX, sinkY, 24 * u, COLOR.green, 'center', 'bold');
    };
  }

  function visualCosine(p, clock) {
    const passages = [{ angle: 0.05, length: 230 }, { angle: 0.42, length: 175 }, { angle: 0.7, length: 260 }, { angle: 1.15, length: 205 }, { angle: -0.45, length: 240 }];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const origin = { x: area.x + area.w * 0.12, y: area.y + area.h * 0.7 };
      const questionAngle = 0.5 + 0.55 * Math.sin(t * 0.8), scores = passages.map(v => Math.cos(v.angle - questionAngle));
      const best = scores.indexOf(Math.max(...scores));
      strokeColor(p, COLOR.line); p.strokeWeight(1); p.line(origin.x - 20 * u, origin.y, origin.x + area.w * 0.5, origin.y);
      passages.forEach((v, i) => {
        const end = { x: origin.x + Math.cos(-v.angle) * v.length * u * 1.1, y: origin.y + Math.sin(-v.angle) * v.length * u * 1.1 };
        arrowBetween(p, origin.x, origin.y, end.x, end.y, i === best ? COLOR.green : COLOR.dim, 11 * u);
      });
      const qEnd = { x: origin.x + Math.cos(-questionAngle) * 270 * u, y: origin.y + Math.sin(-questionAngle) * 270 * u };
      arrowBetween(p, origin.x, origin.y, qEnd.x, qEnd.y, COLOR.amber, 14 * u);
      drawText(p, 'question', qEnd.x + 10 * u, qEnd.y - 18 * u, 18 * u, COLOR.amber, 'left', 'bold');
      // la liste des scores, du plus proche au plus lointain
      const order = scores.map((s, i) => i).sort((a, b) => scores[b] - scores[a]), barX = area.x + area.w * 0.68, barW = area.w * 0.26;
      drawText(p, 'proximité  cos θ', barX, area.y + 10 * u, 18 * u, COLOR.dim, 'left', 'bold');
      order.forEach((i, rank) => {
        const y = area.y + 55 * u + rank * 52 * u, value = Math.max(0, scores[i]);
        fillColor(p, COLOR.card); p.noStroke(); p.rect(barX, y, barW, 30 * u, 8);
        fillColor(p, i === best ? COLOR.green : COLOR.blue, 230); p.rect(barX, y, barW * value, 30 * u, 8);
        drawText(p, `passage ${i + 1}`, barX + 10 * u, y + 15 * u, 16 * u, COLOR.text, 'left', 'bold');
        drawText(p, scores[i].toFixed(2).replace('.', ','), barX + barW - 10 * u, y + 15 * u, 16 * u, COLOR.text, 'right', 'bold');
      });
    };
  }

  function visualFourRules(p, clock) {
    const rules = [
      { title: 'Rester dans le passage', symbol: 'circle' }, { title: 'Copier mot à mot', symbol: 'quote' },
      { title: 'null plutôt qu\'inventer', symbol: 'empty' }, { title: 'Le texte est une donnée', symbol: 'lock' },
    ];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      rules.forEach((rule, i) => {
        const shown = reveal(t, 0.4 + i * 1.6), col = i % 2, row = Math.floor(i / 2);
        const cx = area.x + area.w * (0.27 + 0.46 * col), cy = area.y + area.h * (0.25 + 0.5 * row) + (1 - shown) * 30;
        drawCard(p, cx - 230 * u, cy - 84 * u, 460 * u, 168 * u, COLOR.green, 255 * shown);
        p.push(); p.translate(cx - 140 * u, cy); strokeColor(p, COLOR.green, 255 * shown); p.strokeWeight(5); p.noFill();
        if (rule.symbol === 'circle') { p.circle(0, 0, 90 * u); fillColor(p, COLOR.green, 255 * shown); p.circle(10 * u, 6 * u, 18 * u); }
        if (rule.symbol === 'quote') { fillColor(p, COLOR.green, 255 * shown); p.noStroke(); p.textSize(130 * u); p.textAlign(p.CENTER, p.CENTER); p.text('“”', 0, 14 * u); }
        if (rule.symbol === 'empty') { p.circle(0, 0, 80 * u); p.line(-48 * u, 48 * u, 48 * u, -48 * u); }
        if (rule.symbol === 'lock') { p.rectMode(p.CENTER); p.rect(0, 14 * u, 76 * u, 58 * u, 8); p.arc(0, -16 * u, 46 * u, 54 * u, Math.PI, 0); p.rectMode(p.CORNER); }
        p.pop();
        drawText(p, rule.title, cx - 70 * u, cy, 25 * u, COLOR.text, 'left', 'bold');
        drawText(p, String(i + 1), cx + 205 * u, cy - 62 * u, 24 * u, COLOR.dim, 'right', 'bold');
      });
    };
  }

  function visualContract(p, clock) {
    const bad = [['crop_original', '"Vigne"', true], ['dose_value', '"1,5 L/ha"', false], ['dose_unit', '"L/ha"', true], ['invente', 'true', false]];
    const good = [['crop_original', '"Vigne"', true], ['dose_value', '0.5', true], ['dose_unit', '"kg/ha"', true], ['quote', '"Dose retenue: 0.5 kg/ha"', true]];
    const reasons = { dose_value: 'nombre attendu, texte reçu', invente: 'champ interdit' };
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const panels = [{ x: 0.27, rows: bad, accepted: false, start: 0.4, title: 'Réponse du modèle' }, { x: 0.73, rows: good, accepted: true, start: 8, title: 'Après correction' }];
      panels.forEach(panel => {
        const shown = reveal(t, panel.start - 0.3), cx = p.width * panel.x, top = area.y + 30 * u;
        drawCard(p, cx - 250 * u, top, 500 * u, 330 * u, panel.accepted ? COLOR.green : COLOR.red, 255 * shown);
        drawText(p, panel.title, cx, top + 30 * u, 20 * u, COLOR.dim, 'center', 'bold');
        panel.rows.forEach(([field, value, valid], i) => {
          const rowShown = reveal(t, panel.start + i * 0.9), y = top + 85 * u + i * 58 * u;
          drawText(p, `${field}: ${value}`, cx - 230 * u, y, 19 * u, [COLOR.text[0], COLOR.text[1], COLOR.text[2]], 'left');
          if (rowShown > 0.5) {
            const color = valid ? COLOR.green : COLOR.red;
            drawText(p, valid ? '✓' : '✗', cx + 225 * u, y, 30 * u, color, 'right', 'bold');
            if (!valid) drawText(p, reasons[field] || '', cx + 200 * u, y + 24 * u, 14 * u, COLOR.red, 'right');
          }
        });
      });
      if (t > 5.5) drawText(p, `${L.performance.refused_by_pydantic} réponses refusées au total`, p.width / 2, area.y + area.h * 0.97, 26 * u, COLOR.red, 'center', 'bold');
      arrowBetween(p, p.width * 0.27 + 270 * u, area.y + 190 * u, p.width * 0.73 - 270 * u, area.y + 190 * u, COLOR.amber, 12 * u);
    };
  }

  function visualProof(p, clock) {
    const example = L.cases[0] ? L.cases[0].trace : null;
    const passageText = example ? example.passage.text : '';
    const realQuote = example && example.record ? example.record.citation.quote : passageText.split(' ').slice(0, 4).join(' ');
    const fakeQuote = realQuote.replace(/\d+(?:[.,]\d+)?/, m => (parseFloat(m.replace(',', '.')) + 0.7).toFixed(1));
    const words = passageText.split(/\s+/), normal = s => s.toLowerCase();
    function locate(quote) {
      const target = quote.split(/\s+/).map(normal);
      for (let i = 0; i + target.length <= words.length; i++) if (target.every((w, k) => normal(words[i + k]) === w)) return [i, i + target.length - 1];
      return null;
    }
    const realSpan = locate(realQuote), fakeSpan = locate(fakeQuote);
    let layout = null;
    function layoutWords(area, size) {
      p.textSize(size); p.textStyle(p.NORMAL);
      let x = area.x, y = area.y + 120 * unit(p); const gap = p.textWidth(' ') + 2, lines = [];
      words.forEach((word, i) => { const w = p.textWidth(word); if (x + w > area.x + area.w) { x = area.x; y += size * 1.7; } lines.push({ word, x, y, w, i }); x += w + gap; });
      return lines;
    }
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      layout = layout || layoutWords(area, 18 * u);
      const phase = t < 9 ? 0 : 1, local = phase === 0 ? t : t - 9, claim = phase === 0 ? realQuote : fakeQuote, span = phase === 0 ? realSpan : fakeSpan;
      drawText(p, `Citation proposée : « ${claim} »`, area.x, area.y + 40 * u, 22 * u, phase === 0 ? COLOR.green : COLOR.red, 'left', 'bold');
      const scanned = Math.min(words.length, Math.floor(local * 9)), found = span && scanned > span[1], finished = scanned >= words.length;
      layout.forEach(item => {
        const inSpan = span && item.i >= span[0] && item.i <= span[1];
        if (found && inSpan) { fillColor(p, COLOR.green, 90); p.noStroke(); p.rect(item.x - 3, item.y - 14 * u, item.w + 6, 28 * u, 5); }
        else if (item.i === scanned && !finished) { fillColor(p, COLOR.amber, 140); p.noStroke(); p.rect(item.x - 3, item.y - 14 * u, item.w + 6, 28 * u, 5); }
        drawText(p, item.word, item.x, item.y, 18 * u, item.i <= scanned ? COLOR.text : COLOR.dim, 'left');
      });
      const verdictY = layout[layout.length - 1].y + 70 * u;
      if (found) drawText(p, '✓ retrouvée mot à mot : acceptée', area.x, verdictY, 30 * u, COLOR.green, 'left', 'bold');
      else if (finished) drawText(p, '✗ introuvable dans le texte : refusée', area.x, verdictY, 30 * u, COLOR.red, 'left', 'bold');
    };
  }

  function visualCumulative(p, clock) {
    const attempts = L.eval.essais_par_passage, total = L.performance.passages;
    const second = attempts['2'] || 0, third = L.performance.rescued_by_retry - second;
    const bars = [
      { label: '1 essai', count: L.performance.first_try, color: COLOR.green },
      { label: '≤ 2 essais', count: L.performance.first_try + second, color: COLOR.green },
      { label: '≤ 3 essais', count: L.performance.published, color: COLOR.green },
      { label: 'expert', count: L.performance.sent_to_expert, color: COLOR.red },
    ];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const baseY = area.y + area.h * 0.78, maxHeight = area.h * 0.62, barW = area.w * 0.15;
      bars.forEach((bar, i) => {
        const shown = reveal(t, 0.5 + i * 2.2, 1.4), x = area.x + area.w * (0.1 + i * 0.22), height = maxHeight * (bar.count / total) * shown;
        fillColor(p, bar.color, 230); p.noStroke(); p.rect(x, baseY - height, barW, height, 8);
        drawText(p, `${frNumber(100 * bar.count / total * shown, 1)} %`, x + barW / 2, baseY - height - 24 * u, 28 * u, bar.color, 'center', 'bold');
        drawText(p, bar.label, x + barW / 2, baseY + 28 * u, 21 * u, COLOR.text, 'center', 'bold');
        drawText(p, `${Math.round(bar.count * shown)} passages`, x + barW / 2, baseY + 56 * u, 16 * u, COLOR.dim);
      });
      drawText(p, 'P(réussite ≤ k essais)', area.x + area.w * 0.5, area.y + 6 * u, 20 * u, COLOR.dim, 'center', 'bold');
    };
  }

  function visualFunnel(p, clock) {
    const attempts = Object.entries(L.eval.essais_par_passage).reduce((sum, [k, v]) => sum + Number(k) * v, 0);
    const accepted = L.performance.published, pydantic = L.performance.refused_by_pydantic, proof = L.performance.refused_by_proof_check;
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const rows = [
        { label: 'Réponses du modèle', value: attempts, color: COLOR.blue, start: 0.4 },
        { label: 'Arrêtées par Pydantic', value: pydantic, color: COLOR.amber, start: 3 },
        { label: 'Arrêtées par la preuve', value: proof, color: COLOR.red, start: 5 },
        { label: 'Publiées', value: accepted, color: COLOR.green, start: 7.5 },
      ];
      rows.forEach((row, i) => {
        const shown = reveal(t, row.start, 1.1), y = area.y + 6 * u + i * area.h * 0.245, fullWidth = area.w * 0.62;
        drawText(p, row.label, area.x, y + 30 * u, 23 * u, COLOR.text, 'left', 'bold');
        fillColor(p, COLOR.card); p.noStroke(); p.rect(area.x + area.w * 0.3, y, fullWidth, 60 * u, 10);
        fillColor(p, row.color, 230); p.rect(area.x + area.w * 0.3, y, fullWidth * (row.value / attempts) * shown, 60 * u, 10);
        drawText(p, String(Math.round(row.value * shown)), area.x + area.w * 0.3 + fullWidth * (row.value / attempts) * shown + 14 * u, y + 30 * u, 30 * u, row.color, 'left', 'bold');
      });
    };
  }

  function visualResults(p, clock) {
    const evaluation = L.eval, performance_ = L.performance;
    const figures = [
      { value: Math.round(100 * performance_.published_rate), suffix: ' %', label: 'passages publiés avec preuve', color: COLOR.green },
      { value: Math.round(100 * evaluation.exactitude_par_champ.dose_value), suffix: ' %', label: 'de doses exactes', color: COLOR.green },
      { value: evaluation.valeurs_inventees_publiees, suffix: '', label: 'valeur inventée', color: COLOR.green },
      { value: performance_.refused_by_pydantic + performance_.refused_by_proof_check, suffix: '', label: 'erreurs arrêtées', color: COLOR.amber },
    ];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      figures.forEach((figure, i) => {
        const shown = reveal(t, 0.4 + i * 1.5, 1.3), cx = area.x + area.w * (0.14 + 0.24 * i), cy = area.y + area.h * 0.45;
        drawText(p, `${Math.round(figure.value * shown)}${figure.suffix}`, cx, cy, 92 * u, figure.color, 'center', 'bold');
        drawText(p, figure.label, cx, cy + 80 * u, 21 * u, COLOR.text, 'center', 'bold');
      });
      drawText(p, `comparés à la source structurée e-Phy · ${L.eval.records_evalues} enregistrements`, p.width / 2, area.y + area.h * 0.95, 19 * u, COLOR.dim);
    };
  }

  function visualPromptHistory(p, clock) {
    const history = L.prompt_history;
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const panels = [
        { title: 'Renvoyés à l\'expert (moins = mieux)', key: 'sent_to_expert', color: COLOR.red, x: 0.05 },
        { title: 'Réussis du premier coup', key: 'first_try', color: COLOR.green, x: 0.53 },
      ];
      panels.forEach(panel => {
        const maxValue = Math.max(...history.map(h => h[panel.key])), baseY = area.y + area.h * 0.78, left = area.x + area.w * panel.x;
        drawText(p, panel.title, left, area.y + 10 * u, 20 * u, COLOR.dim, 'left', 'bold');
        history.forEach((version, i) => {
          const shown = reveal(t, 0.6 + i * 2.5, 1.2), width = area.w * 0.12, x = left + i * area.w * 0.15, height = area.h * 0.55 * (version[panel.key] / maxValue) * shown;
          fillColor(p, panel.color, 80 + 60 * i); p.noStroke(); p.rect(x, baseY - height, width, height, 8);
          drawText(p, String(Math.round(version[panel.key] * shown)), x + width / 2, baseY - height - 20 * u, 28 * u, panel.color, 'center', 'bold');
          drawText(p, version.version, x + width / 2, baseY + 24 * u, 22 * u, COLOR.text, 'center', 'bold');
        });
      });
      drawText(p, 'v1 : départ · v2 : contrôle plus strict · v3 : règle de citation précisée', p.width / 2, area.y + area.h * 1.0, 18 * u, COLOR.dim);
      if (L.holdout && t > 8) drawText(p, `hors échantillon : ${L.holdout.passages} passages de produits jamais vus · ${Math.round(100 * L.holdout.exactitude_par_champ.dose_value)} % de doses exactes`, p.width / 2, area.y + area.h * 1.1, 24 * u, COLOR.green, 'center', 'bold');
    };
  }

  function visualSovereignty(p, clock) {
    const sources = ['e-Phy', 'PMRA', 'EPA'];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const centerX = p.width * 0.5, centerY = area.y + area.h * 0.5, radius = Math.min(area.h * 0.52, p.width * 0.2);
      strokeColor(p, COLOR.green); p.strokeWeight(3); p.drawingContext.setLineDash([12, 8]); fillColor(p, COLOR.green, 18); p.circle(centerX, centerY, radius * 2); p.drawingContext.setLineDash([]);
      drawText(p, 'CONSTELLATION ASTROPORT.ONE', centerX, centerY - radius + 24 * u, 15 * u, COLOR.green, 'center', 'bold');
      [['RTX 3090', COLOR.blue, -0.55, 0.1], ['Qdrant', COLOR.amber, 0.55, 0.1], ['traces', COLOR.dim, 0, 0.55]].forEach(([name, color, dx, dy]) => {
        const x = centerX + dx * radius, y = centerY + dy * radius; drawCard(p, x - 60 * u, y - 24 * u, 120 * u, 48 * u, color); drawText(p, name, x, y, 18 * u, COLOR.text, 'center', 'bold');
      });
      sources.forEach((name, i) => {
        const y = area.y + area.h * (0.22 + i * 0.28), x = area.x + 50 * u;
        drawCard(p, x - 50 * u, y - 22 * u, 100 * u, 44 * u, COLOR.line); drawText(p, name, x, y, 17 * u, COLOR.text, 'center', 'bold');
        arrowBetween(p, x + 56 * u, y, centerX - radius * 0.98, centerY + (i - 1) * radius * 0.35, COLOR.green, 9 * u);
        const phase = (t * 0.4 + i / 3) % 1; fillColor(p, COLOR.green); p.noStroke(); p.circle(p.lerp(x + 56 * u, centerX - radius, phase), p.lerp(y, centerY + (i - 1) * radius * 0.35, phase), 10 * u);
      });
      const cloudX = p.width * 0.86, cloudY = area.y + area.h * 0.28;
      fillColor(p, COLOR.dim, 60); strokeColor(p, COLOR.dim); p.strokeWeight(2); p.ellipse(cloudX, cloudY, 150 * u, 80 * u); p.ellipse(cloudX - 40 * u, cloudY + 12 * u, 80 * u, 60 * u); p.ellipse(cloudX + 40 * u, cloudY + 12 * u, 80 * u, 60 * u);
      drawText(p, 'IA cloud', cloudX, cloudY + 6 * u, 20 * u, COLOR.dim, 'center', 'bold');
      p.drawingContext.setLineDash([8, 8]); strokeColor(p, COLOR.red); p.strokeWeight(3); p.line(centerX + radius, centerY - radius * 0.3, cloudX - 80 * u, cloudY + 20 * u); p.drawingContext.setLineDash([]);
      strokeColor(p, COLOR.red); p.strokeWeight(7); const mx = (centerX + radius + cloudX - 80 * u) / 2, my = (centerY - radius * 0.3 + cloudY + 20 * u) / 2;
      p.line(mx - 18 * u, my - 18 * u, mx + 18 * u, my + 18 * u); p.line(mx - 18 * u, my + 18 * u, mx + 18 * u, my - 18 * u);
      drawText(p, '0 appel · 0 clé', cloudX, cloudY + 70 * u, 24 * u, COLOR.red, 'center', 'bold');
    };
  }

  function visualSobriety(p, clock) {
    const network = L.network, cold = network.cold, warm = network.warm || network.cold;
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      const maxMb = cold.total_megabytes, barArea = { x: area.x + area.w * 0.2, w: area.w * 0.7 };
      [['1ʳᵉ collecte', cold, COLOR.blue, 0.4], ['Rejeu', warm, COLOR.green, 3.2]].forEach(([name, run, color, start], i) => {
        const shown = reveal(t, start, 1.4), y = area.y + 30 * u + i * 150 * u;
        drawText(p, name, area.x, y + 30 * u, 24 * u, COLOR.text, 'left', 'bold');
        fillColor(p, COLOR.card); p.noStroke(); p.rect(barArea.x, y, barArea.w, 60 * u, 10);
        fillColor(p, color, 230); p.rect(barArea.x, y, Math.max(8, barArea.w * run.total_megabytes / maxMb * shown), 60 * u, 10);
        drawText(p, `${frNumber(run.total_megabytes * shown, 1)} Mo`, barArea.x + 14 * u, y + 30 * u, 28 * u, COLOR.background, 'left', 'bold');
        for (let k = 0; k < run.total_requests; k++) {          // une pastille par requête ; bleu clair = « inchangé »
          const unchanged = k < run.not_modified; fillColor(p, unchanged ? COLOR.green : COLOR.blue, 230 * shown); p.circle(barArea.x + 14 * u + k * 34 * u, y + 94 * u, 20 * u);
        }
      });
      drawText(p, `${cold.total_requests} requêtes au total · vert = réponse « inchangé », rien retéléchargé`, p.width / 2, area.y + area.h * 0.98, 20 * u, COLOR.dim);
    };
  }

  function visualVram(p, clock) {
    const bench = L.bench, facts = bench.results[bench.recommendation.model].facts, overhead = 0.8;
    const gpus = [[8, 'RTX 4060 · 8 Go'], [16, 'RTX 4060 Ti · 16 Go'], [24, 'RTX 3090 · 24 Go']];
    let touched = false, parallelSlider, contextSlider;
    const host_ = host;
    function addSlider(min, max, value, step, leftShare) {
      const area = drawingArea(p), slider = p.createSlider(min, max, value, step); slider.parent(host_); slider.position(area.x + area.w * leftShare, area.y + area.h * 0.9); slider.style('width', '200px');
      slider.input(() => { touched = true; }); return slider;
    }
    p.setupExtras = () => { parallelSlider = addSlider(1, 8, 1, 1, 0.0); contextSlider = addSlider(2048, 16384, 4096, 2048, 0.3); };
    p.draw = () => {
      if (!parallelSlider) p.setupExtras();
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      if (!touched) { parallelSlider.value(1 + Math.floor((t * 0.45) % 8)); contextSlider.value(4096); }
      const parallel = parallelSlider.value(), context = contextSlider.value();
      const weights = facts.disk_gb, cache = facts.kv_bytes_per_token * context * parallel / 1e9, total = weights + cache + overhead;
      const scale = area.h * 0.8 / 26, baseY = area.y + area.h * 0.97, barX = area.x + area.w * 0.62, barW = area.w * 0.12;
      gpus.forEach(([capacity, name]) => {
        const y = baseY - capacity * scale; strokeColor(p, total > capacity ? COLOR.red : COLOR.line); p.strokeWeight(2); p.drawingContext.setLineDash([6, 6]); p.line(barX - 30 * u, y, barX + barW + 30 * u, y); p.drawingContext.setLineDash([]);
        drawText(p, name, barX + barW + 40 * u, y, 17 * u, total > capacity ? COLOR.red : COLOR.dim, 'left', 'bold');
      });
      let y = baseY; [[weights, COLOR.blue], [cache, COLOR.amber], [overhead, COLOR.dim]].forEach(([value, color]) => { fillColor(p, color, 230); p.noStroke(); p.rect(barX, y - value * scale, barW, value * scale); y -= value * scale; });
      drawText(p, `${frNumber(total, 1)} Go`, barX + barW / 2, y - 24 * u, 34 * u, COLOR.green, 'center', 'bold');
      const lines = [[`poids du modèle`, weights, COLOR.blue], [`cache d'attention`, cache, COLOR.amber], [`marge`, overhead, COLOR.dim]];
      lines.forEach(([name, value, color], i) => { drawText(p, `${i ? '+' : ''} ${name}`, area.x, area.y + 30 * u + i * 46 * u, 24 * u, color, 'left', 'bold'); drawText(p, `${frNumber(value, 2)} Go`, area.x + area.w * 0.4, area.y + 30 * u + i * 46 * u, 24 * u, COLOR.text, 'right', 'bold'); });
      drawText(p, `cache = 2 × couches × têtes KV × dim × 2 octets × ${context} × ${parallel}`, area.x, area.y + 190 * u, 16 * u, COLOR.dim, 'left');
      drawText(p, `requêtes en parallèle : ${parallel}`, area.x, area.y + area.h * 0.84, 18 * u, COLOR.text, 'left', 'bold');
      drawText(p, `contexte : ${context}`, area.x + area.w * 0.3, area.y + area.h * 0.84, 18 * u, COLOR.text, 'left', 'bold');
    };
  }

  function visualThroughput(p, clock) {
    const bench = L.bench, efficiency = bench.service.efficiency_measured, bandwidth = bench.service.gpu_bandwidth_gb_s, models = Object.values(bench.results);
    const maxSpeed = Math.max(...models.map(m => Math.max(m.decode_tok_s, efficiency * bandwidth / m.facts.disk_gb)));
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      drawText(p, `tok/s ≈ ${frNumber(efficiency, 2)} × ${bandwidth} Go/s ÷ poids`, p.width / 2, area.y + 8 * u, 28 * u, COLOR.green, 'center', 'bold');
      models.forEach((model, i) => {
        const shown = reveal(t, 0.8 + i * 1.8, 1.2), y = area.y + 58 * u + i * area.h * 0.3, chosen = model.model === bench.recommendation.model;
        const predicted = efficiency * bandwidth / model.facts.disk_gb, left = area.x + area.w * 0.22, width = area.w * 0.7;
        drawText(p, model.model.replace(':latest', ''), area.x, y + 26 * u, 24 * u, chosen ? COLOR.green : COLOR.text, 'left', 'bold');
        drawText(p, `${model.facts.disk_gb} Go · ${model.accepted}/${model.passages} acceptés`, area.x, y + 56 * u, 16 * u, COLOR.dim, 'left');
        fillColor(p, COLOR.card); p.noStroke(); p.rect(left, y, width, 52 * u, 10);
        fillColor(p, chosen ? COLOR.green : COLOR.blue, 230); p.rect(left, y, width * model.decode_tok_s / maxSpeed * shown, 52 * u, 10);
        drawText(p, `${Math.round(model.decode_tok_s * shown)} tok/s mesurés`, left + 12 * u, y + 26 * u, 22 * u, COLOR.background, 'left', 'bold');
        const markerX = left + width * predicted / maxSpeed * shown; strokeColor(p, COLOR.amber); p.strokeWeight(5); p.line(markerX, y - 8 * u, markerX, y + 60 * u);
        if (shown > 0.95) drawText(p, `formule ${Math.round(predicted)}`, markerX, y - 20 * u, 15 * u, COLOR.amber, 'center', 'bold');
      });
    };
  }

  function visualCost(p, clock) {
    const cost = L.cost, scenario = cost.scenarios[2].name, options = cost.options;
    const apis = options.filter(o => o.kind !== 'local'), cheapest = apis.reduce((m, o) => o.totals[scenario] < m.totals[scenario] ? o : m);
    const pick = text => options.find(o => o.kind === 'api' && o.label.includes(text));
    const rows = [
      { name: 'Local · électricité', value: options[0].totals[scenario], color: COLOR.green }, { name: 'Local · avec amortissement', value: options[1].totals[scenario], color: COLOR.green },
      { name: cheapest.label.replace(' (Batch, −50 %)', ' · lot'), value: cheapest.totals[scenario], color: COLOR.blue },
      { name: 'Claude Sonnet 5.5', value: pick('Sonnet').totals[scenario], color: COLOR.amber }, { name: 'Claude Opus 5.5', value: pick('Opus').totals[scenario], color: COLOR.red },
      { name: 'gpt-5.5', value: pick('gpt-5.5').totals[scenario], color: COLOR.red },
    ];
    const logMin = 0.7, logMax = 4.2, position = v => (Math.log10(Math.max(v, 1)) - logMin) / (logMax - logMin);
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p), left = area.x + area.w * 0.27, width = area.w * 0.68;
      p.background(COLOR.background);
      [10, 100, 1000, 10000].forEach(tick => { const x = left + width * position(tick); strokeColor(p, COLOR.line); p.strokeWeight(1); p.line(x, area.y, x, area.y + area.h * 0.94); drawText(p, `${frNumber(tick)} $`, x, area.y + area.h * 0.99, 16 * u, COLOR.dim); });
      rows.forEach((row, i) => {
        const shown = reveal(t, 0.5 + i * 1.5, 1.1), y = area.y + 4 * u + i * area.h * 0.155;
        drawText(p, row.name, area.x, y + 20 * u, 19 * u, COLOR.text, 'left', 'bold');
        fillColor(p, row.color, 230); p.noStroke(); p.rect(left, y, Math.max(6, width * position(row.value) * shown), 40 * u, 8);
        drawText(p, `${frNumber(row.value, row.value < 100 ? 0 : 0)} $`, left + width * position(row.value) * shown + 12 * u, y + 20 * u, 24 * u, row.color, 'left', 'bold');
      });
      drawText(p, `échelle logarithmique · ${frNumber(cost.scenarios[2].passages)} passages`, p.width / 2, area.y + area.h * 1.07, 18 * u, COLOR.dim);
    };
  }

  function visualLimits(p, clock) {
    const items = [
      ['✓', COLOR.green, '3 sources · 2 régions'], ['✓', COLOR.green, 'preuve et traçabilité'], ['✓', COLOR.green, 'produits sœurs (hypothèses)'],
      ['◐', COLOR.amber, 'Microsoft 365 : documenté'], ['✗', COLOR.dim, 'Brésil (AGROFIT)'], ['✗', COLOR.dim, 'alertes d\'expiration'], ['✗', COLOR.dim, 'codes EPPO officiels'],
    ];
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p);
      p.background(COLOR.background);
      items.forEach(([symbol, color, text], i) => {
        const shown = reveal(t, 0.3 + i * 1.1, 0.6), y = area.y + 14 * u + i * area.h * 0.14;
        drawText(p, symbol, area.x + 30 * u, y, 40 * u, color, 'center', 'bold');
        drawText(p, text, area.x + 80 * u, y, 30 * u, [color[0], color[1], color[2]], 'left', 'bold');
        if (shown < 1) { fillColor(p, COLOR.background, 255 * (1 - shown)); p.noStroke(); p.rect(area.x, y - 30 * u, area.w * 0.6, 60 * u); }
      });
      const badgeShown = reveal(t, 9, 1);
      p.push(); p.translate(area.x + area.w * 0.82, area.y + area.h * 0.45); p.rotate(-0.08);
      strokeColor(p, COLOR.green, 255 * badgeShown); p.strokeWeight(5); fillColor(p, COLOR.green, 25 * badgeShown); p.rect(-150 * u, -75 * u, 300 * u, 150 * u, 18);
      drawText(p, 'AGPL-3.0', 0, -12 * u, 48 * u, COLOR.green, 'center', 'bold'); drawText(p, 'code libre', 0, 40 * u, 24 * u, COLOR.text, 'center');
      p.pop();
    };
  }

  function visualConclusion(p, clock) {
    p.draw = () => {
      const t = clock(), u = unit(p), area = drawingArea(p), cy = area.y + area.h * 0.3;
      p.background(COLOR.background);
      const a = reveal(t, 0.3), b = reveal(t, 2.2);
      drawText(p, 'L\'IA propose.', p.width / 2, cy, 78 * u, COLOR.blue, 'center', 'bold');
      fillColor(p, COLOR.background, 255 * (1 - a)); p.noStroke(); p.rect(0, cy - 60 * u, p.width, 120 * u);
      drawText(p, 'Le code décide.', p.width / 2, cy + 100 * u * b, 78 * u, COLOR.green, 'center', 'bold');
      const facts = [[`${Math.round(100 * L.performance.published_rate)} %`, 'publiés avec preuve'], ['0', 'valeur inventée'], ['0', 'appel à une IA cloud']];
      facts.forEach(([value, text], i) => { const shown = reveal(t, 4 + i * 0.8), x = p.width * (0.25 + 0.25 * i); drawText(p, value, x, area.y + area.h * 0.78, 56 * u * shown, COLOR.text, 'center', 'bold'); drawText(p, text, x, area.y + area.h * 0.78 + 50 * u, 19 * u, COLOR.dim); });
      drawText(p, 'Questions ?', p.width / 2, area.y + area.h * 1.02, 30 * u, COLOR.amber, 'center', 'bold');
    };
  }

  // ── Les 20 diapositives : quelques mots + un visuel ────────────────────────

  const performanceFigures = L.performance, network = L.network;
  const SLIDES = [
    { headline: 'L\'IA propose. Le code décide.', caption: 'Veille réglementaire PPP', visual: visualTitle },
    { headline: 'Des bases dispersées', caption: 'Formats, langues, pays : tout diffère', visual: visualDispersion },
    { headline: 'Trois briques maison', caption: 'IA locale · Qdrant · Pydantic', visual: visualThreeBricks },
    { headline: 'La chaîne de contrôle', caption: 'vert publié · orange réessai · rouge expert', visual: visualChain },
    { headline: '3 sources, 2 régions', caption: 'France · Canada · États-Unis', visual: visualSources },
    { headline: 'Le sens, mesuré par un angle', caption: 'cos θ = a·b ÷ (‖a‖ ‖b‖)', visual: visualCosine },
    { headline: 'Quatre règles de prompt', caption: 'simples, testables', visual: visualFourRules },
    { headline: 'Garde-fou n°1 : le contrat', caption: 'Pydantic refuse la mauvaise forme', visual: visualContract },
    { headline: 'Garde-fou n°2 : la preuve', caption: L.code ? `${L.code.proof_check.path.split('/').pop()} · check_proof() · lignes ${L.code.proof_check.start}–${L.code.proof_check.end}` : 'mot à mot, en code', visual: visualProof },
    { headline: 'Le retry corrige', caption: `essais cumulés sur ${performanceFigures.passages} passages`, visual: visualCumulative },
    { headline: `${performanceFigures.refused_by_pydantic + performanceFigures.refused_by_proof_check} erreurs arrêtées`, caption: 'avant toute publication', visual: visualFunnel },
    { headline: 'Résultats mesurés', caption: 'face à la source structurée', visual: visualResults },
    { headline: 'Le prompt s\'améliore', caption: 'comme Arbor : une hypothèse, une mesure', visual: visualPromptHistory },
    { headline: 'Tout reste chez nous', caption: '0 appel à une IA cloud', visual: visualSovereignty },
    { headline: 'Sobre avec les sources', caption: network ? `${network.cold.total_requests} requêtes pour tout collecter` : '', visual: visualSobriety },
    { headline: 'Quelle carte ? Un calcul', caption: 'VRAM = poids + cache + marge', visual: visualVram },
    { headline: 'La vitesse suit une loi', caption: 'efficacité × bande passante ÷ poids', visual: visualThroughput },
    { headline: 'Le coût, en échelle log', caption: `${frNumber(L.cost ? L.cost.scenarios[2].passages : 0)} passages`, visual: visualCost },
    { headline: 'Ce qu\'il reste à faire', caption: 'dit franchement', visual: visualLimits },
    { headline: 'Merci', caption: 'prêts pour vos questions', visual: visualConclusion },
  ];

  // ── Lecteur : 20 s par diapositive, voix, sous-titres ──────────────────────

  const $ = id => document.getElementById(id);
  const host = $('pk-stage');
  const player = { open: false, index: 0, running: false, slideStartedAt: 0, pausedAt: 0, voiceOn: true, subtitles: false, sketch: null };
  const audio = new Audio();
  const pad = n => String(n).padStart(2, '0');

  // Voix : fichier audio préparé (web/audio/pk-NN.mp3), sinon synthèse du navigateur, jamais une voix cloud.
  function localFrenchVoice() {
    return (window.speechSynthesis ? speechSynthesis.getVoices() : []).find(v => v.lang && v.lang.toLowerCase().startsWith('fr') && v.localService);
  }
  function stopVoice() { audio.pause(); if (window.speechSynthesis) speechSynthesis.cancel(); }
  function setVoiceStatus(text) { $('pk-voice-status').textContent = text; }

  function speakWithBrowser(text) {
    const voice = localFrenchVoice();
    if (!voice) { setVoiceStatus('aucune voix française locale : sous-titres'); showSubtitles(true); return; }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice; utterance.lang = 'fr-FR';
    utterance.rate = Math.min(1.25, Math.max(0.9, (text.split(/\s+/).length / 2.6) / (SLIDE_SECONDS - 1)));
    speechSynthesis.speak(utterance); setVoiceStatus(`voix : navigateur (${voice.name})`);
  }

  function startVoice(index) {
    stopVoice();
    if (!player.voiceOn) { setVoiceStatus('voix coupée'); return; }
    const text = (L.narration || [])[index] || '';
    if (!L.audio_available) { speakWithBrowser(text); return; }               // pas de fichier préparé : voix du navigateur
    audio.src = `web/audio/pk-${pad(index + 1)}.mp3`;
    audio.play().then(() => setVoiceStatus('voix : fichier audio préparé')).catch(() => speakWithBrowser(text));
  }

  function showSubtitles(forced) {
    if (forced) player.subtitles = true;
    const box = $('pk-subtitle');
    box.hidden = !player.subtitles; box.textContent = player.subtitles ? (L.narration || [])[player.index] || '' : '';
  }

  function mountSketch() {
    if (player.sketch) player.sketch.remove();
    host.innerHTML = '';
    const slide = SLIDES[player.index];
    try { player.sketch = new p5(sketchOf(slide.visual), host); }
    catch (error) { host.textContent = `Visuel indisponible : ${error.message}`; }
  }

  function showSlide(index, { autoplayVoice }) {
    player.index = Math.max(0, Math.min(SLIDES.length - 1, index));
    const slide = SLIDES[player.index];
    $('pk-headline').textContent = slide.headline; $('pk-caption').textContent = slide.caption;
    $('pk-count').textContent = `${player.index + 1} / ${SLIDES.length}`;
    $('pk-segments').innerHTML = SLIDES.map((_, i) => `<i class="${i < player.index ? 'done' : i === player.index ? 'now' : ''}"></i>`).join('');
    player.slideStartedAt = performance.now(); player.pausedAt = performance.now();
    mountSketch(); showSubtitles(false);
    if (autoplayVoice) startVoice(player.index); else stopVoice();
  }

  function tick() {
    if (!player.open) return;
    const now = performance.now();
    if (player.running) {
      const elapsed = (now - player.slideStartedAt) / 1000;
      $('pk-progress').style.width = `${Math.min(100, elapsed / SLIDE_SECONDS * 100)}%`;
      if (elapsed >= SLIDE_SECONDS && !player.hold) {
        if (player.index < SLIDES.length - 1) showSlide(player.index + 1, { autoplayVoice: true });
        else { player.running = false; $('pk-play').textContent = '▶'; }
      }
    }
    const reference = player.running ? now : player.pausedAt;                // en pause, le chronomètre est figé
    const total = (player.index * SLIDE_SECONDS) + Math.max(0, Math.min(SLIDE_SECONDS, (reference - player.slideStartedAt) / 1000));
    $('pk-clock').textContent = `${Math.floor(total / 60)}:${pad(Math.floor(total % 60))} / 6:40`;
  }

  function setRunning(running) {
    if (running === player.running) return;
    const now = performance.now();
    if (running) {
      player.slideStartedAt += now - player.pausedAt;                       // le temps de pause ne compte pas
      const speaking = window.speechSynthesis && speechSynthesis.speaking;
      if (!player.started) startVoice(player.index);
      else if (audio.src && audio.paused && audio.currentTime > 0) audio.play();
      else if (speaking && speechSynthesis.paused) speechSynthesis.resume();
      player.started = true;
    } else {
      player.pausedAt = now; audio.pause(); if (window.speechSynthesis) speechSynthesis.pause();
    }
    player.running = running; $('pk-play').textContent = running ? '⏸' : '▶'; $('pk-start').hidden = player.started;
  }

  function open() {
    player.open = true; player.started = false; $('pk').hidden = false; document.body.style.overflow = 'hidden';
    player.running = false; $('pk-play').textContent = '▶'; $('pk-start').hidden = false;
    showSlide(0, { autoplayVoice: false });
  }
  // Mode enregistrement (generate_scene.sh) : une diapositive, sans commandes, sans passage automatique à la suivante.
  function present(index) {
    player.open = true; player.started = true; player.voiceOn = false; player.hold = true;
    $('pk').hidden = false; $('pk').classList.add('recording'); $('pk-start').hidden = true; document.body.style.overflow = 'hidden';
    showSlide(index, { autoplayVoice: false }); player.running = true;
  }
  function close() { player.open = false; player.running = false; $('pk').hidden = true; document.body.style.overflow = ''; stopVoice(); if (player.sketch) { player.sketch.remove(); player.sketch = null; } }
  function go(step) { showSlide(player.index + step, { autoplayVoice: player.running }); if (player.running) player.slideStartedAt = performance.now(); }

  // ── Commandes ──────────────────────────────────────────────────────────────

  $('pk-close').onclick = close; $('pk-prev').onclick = () => go(-1); $('pk-next').onclick = () => go(1);
  $('pk-play').onclick = () => setRunning(!player.running); $('pk-start').onclick = () => setRunning(true);
  $('pk-voice').onclick = () => { player.voiceOn = !player.voiceOn; $('pk-voice').classList.toggle('off', !player.voiceOn); if (player.voiceOn && player.running) startVoice(player.index); else stopVoice(); setVoiceStatus(player.voiceOn ? 'voix activée' : 'voix coupée'); };
  $('pk-subs').onclick = () => { player.subtitles = !player.subtitles; showSubtitles(false); };
  $('pk-full').onclick = () => { if (document.fullscreenElement) document.exitFullscreen(); else $('pk').requestFullscreen && $('pk').requestFullscreen(); };
  if (window.speechSynthesis) speechSynthesis.onvoiceschanged = () => {};     // charge la liste des voix locales

  document.addEventListener('keydown', event => {
    if (event.target.matches('input,select,textarea')) return;
    if (event.key === 'p' || event.key === 'P') { player.open ? close() : open(); return; }
    if (!player.open) return;
    if (event.key === 'Escape') close();
    else if (event.key === ' ') { event.preventDefault(); setRunning(!player.running); }
    else if (event.key === 'ArrowRight') go(1); else if (event.key === 'ArrowLeft') go(-1);
    else if (event.key === 'v' || event.key === 'V') $('pk-voice').click();
    else if (event.key === 's' || event.key === 'S') $('pk-subs').click();
    else if (event.key === 'f' || event.key === 'F') $('pk-full').click();
  });

  let resizeTimer;
  window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (player.open) mountSketch(); }, 250); });
  setInterval(tick, 100);

  ['present-open', 'present-open-hero'].forEach(id => { const el = $(id); if (el) el.onclick = open; });
  window.PechaKucha = { open, close, present, slides: SLIDES };
})();
