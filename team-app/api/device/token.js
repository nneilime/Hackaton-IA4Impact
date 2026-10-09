const { send, readBody, handleError, preflight } = require("../_lib/http");

module.exports = async (req, res) => {
  if (preflight(req, res)) return;
  if (req.method !== "POST") return send(res, 405, { error: "Méthode non autorisée" });
  try {
    const clientId = process.env.OAUTH_CLIENT_ID;
    if (!clientId) return send(res, 500, { error: "OAUTH_CLIENT_ID manquant" });

    const { device_code } = await readBody(req);
    if (!device_code) return send(res, 400, { error: "device_code manquant" });

    const params = new URLSearchParams({
      client_id: clientId,
      device_code,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    });
    const gh = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    });
    const data = await gh.json();
    // 200 avec { error: authorization_pending } tant que l'utilisateur n'a pas validé
    return send(res, 200, data);
  } catch (err) {
    return handleError(res, err);
  }
};
