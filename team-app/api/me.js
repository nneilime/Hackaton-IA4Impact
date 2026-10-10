const { send, handleError, guard, authenticate } = require("./_lib/http");
const { getUserEmails, isCollaborator } = require("./_lib/github");
const { hashEmail } = require("./_lib/emailCrypto");

module.exports = async (req, res) => {
  if (guard(req, res)) return;
  try {
    if (req.method !== "GET") return send(res, 405, { error: "Méthode non autorisée" });

    const auth = await authenticate(req);
    if (!auth) return send(res, 401, { error: "Non authentifié" });

    const { user, token } = auth;
    const emails = [...new Set([...(user.email ? [user.email.toLowerCase()] : []), ...(await getUserEmails(token))])];
    const email_hashes = emails.map((e) => hashEmail(e));
    const collaborator = await isCollaborator(user.login);

    return send(res, 200, {
      login: user.login,
      name: user.name,
      avatar_url: user.avatar_url,
      email_hashes,
      isCollaborator: collaborator,
    });
  } catch (err) {
    return handleError(res, err);
  }
};
