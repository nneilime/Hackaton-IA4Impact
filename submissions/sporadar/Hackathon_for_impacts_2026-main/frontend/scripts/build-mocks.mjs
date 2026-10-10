// Convertit mocks/examples.yaml (source de vérité, à la racine du repo) en JSON importable par l'app.
//
// Ce JSON sert à deux choses :
//   1. les tests de gabarits (une réponse d'exemple par type de question)
//   2. le mode « démo hors ligne » (rejouer les exemples si le back tombe)
// Il est versionné : le build Docker n'a pas accès au dossier mocks/ (le contexte est frontend/).
// Si le YAML est introuvable (cas Docker), on garde le JSON existant sans erreur.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, '..', '..', 'mocks', 'examples.yaml');
const target = resolve(here, '..', 'src', 'app', 'core', 'mock', 'examples.json');

if (!existsSync(source)) {
  console.log(`[mocks] ${source} introuvable : ${target} conservé tel quel`);
  process.exit(0);
}

// Chaque clé du YAML est un exemple OpenAPI { summary, value } : on ne garde que la valeur.
const examples = parse(readFileSync(source, 'utf8'));
const values = Object.fromEntries(Object.entries(examples).map(([name, example]) => [name, example.value]));

mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, `${JSON.stringify(values, null, 2)}\n`);
console.log(`[mocks] ${Object.keys(values).length} exemples écrits dans ${target}`);
