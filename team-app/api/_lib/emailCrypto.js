const crypto = require("crypto");

// Clé de 32 octets, fournie via la variable d'environnement EMAIL_SECRET_KEY
// (base64 ou hex). En local, la même clé est stockée hors dépôt, dans le
// dossier parent, par scripts/email-key.js.
function decodeKey(raw) {
  const value = String(raw || "").trim();
  if (!value) {
    const err = new Error("EMAIL_SECRET_KEY manquante");
    err.statusCode = 500;
    throw err;
  }
  const buf = /^[0-9a-fA-F]{64}$/.test(value)
    ? Buffer.from(value, "hex")
    : Buffer.from(value, "base64");
  if (buf.length !== 32) {
    const err = new Error("EMAIL_SECRET_KEY invalide (32 octets attendus)");
    err.statusCode = 500;
    throw err;
  }
  return buf;
}

function getKey() {
  return decodeKey(process.env.EMAIL_SECRET_KEY);
}

function normalizeEmail(email) {
  return String(email || "").trim().toLowerCase();
}

// Empreinte déterministe (sert au matching et à l'affichage).
function hashEmail(email, key) {
  const value = normalizeEmail(email);
  if (!value) return "";
  return crypto.createHmac("sha256", key || getKey()).update(value).digest("hex");
}

// Chiffrement réversible pour permettre aux organisateurs de retrouver l'email.
function encryptEmail(email, key) {
  const value = normalizeEmail(email);
  if (!value) return "";
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key || getKey(), iv);
  const ct = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `v1:${iv.toString("base64")}:${tag.toString("base64")}:${ct.toString("base64")}`;
}

function decryptEmail(payload, key) {
  const parts = String(payload || "").split(":");
  if (parts.length !== 4 || parts[0] !== "v1") {
    const err = new Error("Valeur chiffrée invalide");
    err.statusCode = 500;
    throw err;
  }
  const iv = Buffer.from(parts[1], "base64");
  const tag = Buffer.from(parts[2], "base64");
  const ct = Buffer.from(parts[3], "base64");
  const decipher = crypto.createDecipheriv("aes-256-gcm", key || getKey(), iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ct), decipher.final()]).toString("utf8");
}

module.exports = {
  decodeKey,
  normalizeEmail,
  hashEmail,
  encryptEmail,
  decryptEmail,
};
