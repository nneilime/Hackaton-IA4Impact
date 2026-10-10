const crypto = require("crypto");
const { send, handleError, preflight } = require("../_lib/http");

function base64url(buf) {
  return Buffer.from(buf)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function verifyState(state, secret) {
  const [payload, sig] = String(state || "").split(".");
  if (!payload || !sig) return null;
  const expected = base64url(crypto.createHmac("sha256", secret).update(payload).digest());
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  let data;
  try {
    data = JSON.parse(Buffer.from(payload.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8"));
  } catch {
    return null;
  }
  if (!data.t || Date.now() - data.t > 10 * 60 * 1000) return null;
  return data;
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

    const frontUrl = (process.env.FRONT_URL || "https://nneilime.github.io/Hackaton-IA4Impact").replace(/\/$/, "");
    const redirectBack = (hash) => {
      if (frontUrl) {
        res.statusCode = 302;
        res.setHeader("Location", `${frontUrl}/#${hash}`);
        res.end();
      } else {
        send(res, 500, { error: "FRONT_URL manquant" });
      }
    };

    const url = new URL(req.url, "http://localhost");
    const error = url.searchParams.get("error");
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");

    if (error) return redirectBack("error=" + encodeURIComponent(error));

    const secret = process.env.STATE_SECRET || process.env.GH_ADMIN_TOKEN;
    if (!secret || !verifyState(state, secret)) {
      return redirectBack("error=" + encodeURIComponent("state_invalide"));
    }
    if (!code) return redirectBack("error=" + encodeURIComponent("code_manquant"));

    const clientId = process.env.OAUTH_CLIENT_ID;
    const clientSecret = process.env.OAUTH_CLIENT_SECRET;
    if (!clientId || !clientSecret) {
      return redirectBack("error=" + encodeURIComponent("config_oauth_manquante"));
    }

    const redirectUri = `${origin(req)}/api/auth/callback`;
    const params = new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      code,
      redirect_uri: redirectUri,
    });

    const gh = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    });
    const data = await gh.json();

    if (data.access_token) {
      return redirectBack("access_token=" + encodeURIComponent(data.access_token));
    }
    return redirectBack("error=" + encodeURIComponent(data.error || "oauth_echec"));
  } catch (err) {
    return handleError(res, err);
  }
};
