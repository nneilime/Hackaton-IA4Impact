const crypto = require("crypto");
const { send, handleError, preflight } = require("../_lib/http");

function base64url(buf) {
  return Buffer.from(buf)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function signState(secret) {
  const payload = base64url(JSON.stringify({ n: crypto.randomBytes(16).toString("hex"), t: Date.now() }));
  const sig = base64url(crypto.createHmac("sha256", secret).update(payload).digest());
  return `${payload}.${sig}`;
}

function origin(req) {
  const proto = req.headers["x-forwarded-proto"] || "https";
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  return `${proto}://${host}`;
}

module.exports = async (req, res) => {
  if (preflight(req, res)) return;
  try {
    if (req.method !== "GET") return send(res, 405, { error: "Méthode non autorisée" });

    const clientId = process.env.OAUTH_CLIENT_ID;
    const secret = process.env.STATE_SECRET || process.env.GH_ADMIN_TOKEN;
    if (!clientId) return send(res, 500, { error: "OAUTH_CLIENT_ID manquant" });
    if (!secret) return send(res, 500, { error: "Secret d'état manquant (STATE_SECRET ou GH_ADMIN_TOKEN)" });

    // Toujours dériver l'URL de callback de l'hôte réel de la requête, pour
    // garantir qu'elle correspond exactement à la callback enregistrée.
    const redirectUri = `${origin(req)}/api/auth/callback`;
    const scope = process.env.OAUTH_SCOPES || "public_repo user:email";

    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      scope,
      state: signState(secret),
      allow_signup: "true",
    });

    res.statusCode = 302;
    res.setHeader("Location", "https://github.com/login/oauth/authorize?" + params.toString());
    res.end();
  } catch (err) {
    return handleError(res, err);
  }
};
