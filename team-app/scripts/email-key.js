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

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (c !== "\r") {
      field += c;
    }
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((v) => v !== ""));
}

function loadParticipants() {
  const raw = fs.readFileSync(path.join(REPO_ROOT, "participants.csv"), "utf8");
  const rows = parseCsv(raw);
  if (!rows.length) return [];
  const header = rows[0].map((h) => String(h).trim());
  return rows.slice(1).map((cells) => {
    const obj = {};
    header.forEach((h, i) => {
      obj[h] = cells[i] != null ? cells[i] : "";
    });
    return obj;
  });
}

const csvEscape = (v) =>
  /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);

function exportEmails() {
  process.env.EMAIL_SECRET_KEY = readKeyFile();
  const { decryptEmail } = require("../api/_lib/emailCrypto");
  const rows = [["email", "login", "team_name"].join(",")];
  for (const p of loadParticipants()) {
    let email = "";
    try {
      if (p.email_enc) email = decryptEmail(p.email_enc);
    } catch {
      email = "";
    }
    rows.push([email, p.login || "", p.team_name || ""].map(csvEscape).join(","));
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
