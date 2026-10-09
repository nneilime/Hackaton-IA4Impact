const { getUser, requireEnv } = require("./github");

function applyCors(req, res) {
  const allowed = process.env.ALLOWED_ORIGIN || "*";
  const origin = req.headers.origin;
  if (allowed === "*") {
    res.setHeader("Access-Control-Allow-Origin", "*");
  } else {
    const list = allowed.split(",").map((s) => s.trim());
    res.setHeader("Access-Control-Allow-Origin", list.includes(origin) ? origin : list[0]);
  }
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Event-Code");
  res.setHeader("Access-Control-Max-Age", "86400");
  res.setHeader("Vary", "Origin");
}

function send(res, status, data) {
  const payload = JSON.stringify(data);
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(payload);
}

function readBody(req) {
  return new Promise((resolve) => {
    if (req.body && typeof req.body === "object") return resolve(req.body);
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 1_000_000) req.destroy();
    });
    req.on("end", () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        resolve({});
      }
    });
  });
}

function checkEventCode(req) {
  const expected = process.env.EVENT_CODE;
  if (!expected) return true;
  const provided = req.headers["x-event-code"];
  return String(provided || "") === String(expected);
}

async function authenticate(req) {
  const header = req.headers.authorization || "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  if (!match) return null;
  const user = await getUser(match[1]);
  if (!user) return null;
  return { token: match[1], user };
}

function handleError(res, err) {
  const status = err && err.statusCode ? err.statusCode : 500;
  if (status >= 500) console.error(err);
  send(res, status, { error: err && err.message ? err.message : "Erreur serveur" });
}

function preflight(req, res) {
  applyCors(req, res);
  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.end();
    return true;
  }
  return false;
}

function guard(req, res) {
  if (preflight(req, res)) return true;
  try {
    requireEnv();
  } catch (err) {
    handleError(res, err);
    return true;
  }
  return false;
}

module.exports = {
  applyCors,
  send,
  readBody,
  checkEventCode,
  authenticate,
  handleError,
  preflight,
  guard,
};
