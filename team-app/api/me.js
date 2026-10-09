const { send, handleError, guard, authenticate } = require("./_lib/http");
const { getUserEmails, isCollaborator } = require("./_lib/github");

module.exports = async (req, res) => {
  if (guard(req, res)) return;
  try {
    if (req.method !== "GET") return send(res, 405, { error: "Méthode non autorisée" });

    const auth = await authenticate(req);
    if (!auth) return send(res, 401, { error: "Non authentifié" });

    const { user, token } = auth;
    const emails = [...new Set([...(user.email ? [user.email.toLowerCase()] : []), ...(await getUserEmails(token))])];
    const collaborator = await isCollaborator(user.login);

    return send(res, 200, {
      login: user.login,
      name: user.name,
      avatar_url: user.avatar_url,
      emails,
      isCollaborator: collaborator,
    });
  } catch (err) {
    return handleError(res, err);
  }
};
