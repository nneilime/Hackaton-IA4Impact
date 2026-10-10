#!/usr/bin/env node
"use strict";

// Gestion de la clé de chiffrement des emails.
//
// La clé vit HORS du dépôt, dans le dossier parent du projet :
//   <parent>/hackathon-email.key
// La même valeur doit être définie dans Vercel sous EMAIL_SECRET_KEY.
//
// Usage :
//   node team-app/scripts/email-key.js init      # génère la clé (si absente) et l'affiche
//   node team-app/scripts/email-key.js export    # déchiffre teams.json et liste les emails
//   node team-app/scripts/email-key.js hash <email>

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "../..");
const KEY_PATH = path.resolve(REPO_ROOT, "../hackathon-email.key");

function readKeyFile() {
  if (!fs.existsSync(KEY_PATH)) {
    const err = new Error(`Clé introuvable : ${KEY_PATH}\nLance d'abord : node team-app/scripts/email-key.js init`);
    err.statusCode = 500;
    throw err;
  }
  return fs.readFileSync(KEY_PATH, "utf8").trim();
}

function init() {
  if (fs.existsSync(KEY_PATH)) {
    console.log(`Clé déjà présente : ${KEY_PATH}`);
  } else {
    fs.writeFileSync(KEY_PATH, crypto.randomBytes(32).toString("base64") + "\n", { mode: 0o600 });
    console.log(`Clé générée : ${KEY_PATH}`);
  }
  console.log("\nÀ définir dans Vercel (variable EMAIL_SECRET_KEY) :\n");
  console.log(fs.readFileSync(KEY_PATH, "utf8").trim());
}

function loadStore() {
  const raw = fs.readFileSync(path.join(REPO_ROOT, "teams.json"), "utf8");
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed.teams)) parsed.teams = [];
  return parsed;
}

function exportEmails() {
  process.env.EMAIL_SECRET_KEY = readKeyFile();
  const { decryptEmail } = require("../api/_lib/emailCrypto");
  const store = loadStore();
  const rows = [["email", "login", "team_slug", "team_name", "status"].join(",")];
  for (const team of store.teams) {
    for (const m of team.members || []) {
      const email = m && typeof m === "object" && m.email_enc ? decryptEmail(m.email_enc) : "";
      rows.push(
        [email, (m && m.login) || "", team.slug, team.name, m && m.joined ? "joined" : "invited"]
          .map((v) => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v))
          .join(",")
      );
    }
  }
  console.log(rows.join("\n"));
}

function hashArg(email) {
  process.env.EMAIL_SECRET_KEY = readKeyFile();
  const { hashEmail } = require("../api/_lib/emailCrypto");
  console.log(hashEmail(email));
}

const [, , command, arg] = process.argv;
try {
  if (command === "init") init();
  else if (command === "export") exportEmails();
  else if (command === "hash") {
    if (!arg) throw new Error("Usage : node team-app/scripts/email-key.js hash <email>");
    hashArg(arg);
  } else {
    console.log("Commandes : init | export | hash <email>");
  }
} catch (err) {
  console.error(err.message);
  process.exit(1);
}
