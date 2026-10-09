const { send, handleError, preflight } = require("../_lib/http");

const SCOPES = process.env.OAUTH_SCOPES || "repo user:email";

module.exports = async (req, res) => {
  if (preflight(req, res)) return;
  if (req.method !== "POST") return send(res, 405, { error: "Méthode non autorisée" });
  try {
    const clientId = process.env.OAUTH_CLIENT_ID;
    if (!clientId) return send(res, 500, { error: "OAUTH_CLIENT_ID manquant" });

    const params = new URLSearchParams({ client_id: clientId, scope: SCOPES });
    const gh = await fetch("https://github.com/login/device/code", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    });
    const data = await gh.json();
    return send(res, gh.status, data);
  } catch (err) {
    return handleError(res, err);
  }
};
