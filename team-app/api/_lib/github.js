const GITHUB_API = "https://api.github.com";

const OWNER = process.env.GH_OWNER;
const REPO = process.env.GH_REPO;
const ADMIN_TOKEN = process.env.GH_ADMIN_TOKEN;
const DEFAULT_BRANCH = process.env.GH_BRANCH || "main";

function githubHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "hackathon-ia4impact-team-app",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function github(path, { method = "GET", token = ADMIN_TOKEN, body } = {}) {
  const headers = githubHeaders(token);
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(GITHUB_API + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  return { status: res.status, data };
}

async function getUser(userToken) {
  const { status, data } = await github("/user", { token: userToken });
  if (status !== 200) return null;
  return data;
}

async function getUserEmails(userToken) {
  const { status, data } = await github("/user/emails", { token: userToken });
  if (status !== 200 || !Array.isArray(data)) return [];
  return data
    .filter((e) => e.verified)
    .map((e) => String(e.email).toLowerCase());
}

function userEmails(user) {
  const emails = [];
  if (user && user.email) emails.push(String(user.email).toLowerCase());
  return emails;
}

const REQUIRED_ENV = ["GH_OWNER", "GH_REPO", "GH_ADMIN_TOKEN"];

function requireEnv() {
  const missing = REQUIRED_ENV.filter((k) => !process.env[k]);
  if (missing.length) {
    const err = new Error(`Variables d'environnement manquantes : ${missing.join(", ")}`);
    err.statusCode = 500;
    throw err;
  }
}

function slugify(name) {
  return String(name)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

async function readTeams() {
  const { status, data } = await github(
    `/repos/${OWNER}/${REPO}/contents/teams.json?ref=${encodeURIComponent(DEFAULT_BRANCH)}`
  );
  if (status === 404) return { teams: [] };
  if (status !== 200) {
    const err = new Error("Lecture de teams.json impossible");
    err.statusCode = 502;
    throw err;
  }
  const decoded = Buffer.from(data.content, "base64").toString("utf8");
  try {
    const parsed = JSON.parse(decoded);
    if (!Array.isArray(parsed.teams)) parsed.teams = [];
    return parsed;
  } catch {
    return { teams: [] };
  }
}

async function commitFiles(changes, message, attempt = 0) {
  const ref = await github(`/repos/${OWNER}/${REPO}/git/ref/heads/${DEFAULT_BRANCH}`);
  if (ref.status !== 200) {
    const err = new Error("Branche introuvable");
    err.statusCode = 502;
    throw err;
  }
  const baseCommitSha = ref.data.object.sha;
  const baseCommit = await github(`/repos/${OWNER}/${REPO}/git/commits/${baseCommitSha}`);
  const baseTreeSha = baseCommit.data.tree.sha;

  const tree = [];
  for (const [path, content] of Object.entries(changes)) {
    if (content === null) {
      tree.push({ path, mode: "100644", type: "blob", sha: null });
      continue;
    }
    const blob = await github(`/repos/${OWNER}/${REPO}/git/blobs`, {
      method: "POST",
      body: { content, encoding: "utf-8" },
    });
    if (blob.status !== 201) {
      const err = new Error("Création de blob impossible");
      err.statusCode = 502;
      throw err;
    }
    tree.push({ path, mode: "100644", type: "blob", sha: blob.data.sha });
  }

  const newTree = await github(`/repos/${OWNER}/${REPO}/git/trees`, {
    method: "POST",
    body: { base_tree: baseTreeSha, tree },
  });
  if (newTree.status !== 201) {
    const err = new Error("Création d'arbre impossible");
    err.statusCode = 502;
    throw err;
  }
  const newCommit = await github(`/repos/${OWNER}/${REPO}/git/commits`, {
    method: "POST",
    body: { message, tree: newTree.data.sha, parents: [baseCommitSha] },
  });
  if (newCommit.status !== 201) {
    const err = new Error("Création de commit impossible");
    err.statusCode = 502;
    throw err;
  }
  const update = await github(`/repos/${OWNER}/${REPO}/git/refs/heads/${DEFAULT_BRANCH}`, {
    method: "PATCH",
    body: { sha: newCommit.data.sha, force: false },
  });
  if (update.status === 422 && attempt < 3) {
    return commitFiles(changes, message, attempt + 1);
  }
  if (update.status !== 200) {
    const err = new Error("Mise à jour de la branche impossible");
    err.statusCode = 502;
    throw err;
  }
  return newCommit.data;
}

async function inviteCollaborator(login) {
  if (!login) return { status: 0 };
  const { status } = await github(
    `/repos/${OWNER}/${REPO}/collaborators/${encodeURIComponent(login)}`,
    { method: "PUT", body: { permission: "push" } }
  );
  return { status };
}

async function isCollaborator(login) {
  const { status } = await github(
    `/repos/${OWNER}/${REPO}/collaborators/${encodeURIComponent(login)}`
  );
  return status === 204;
}

function teamMemberLogins(team) {
  return (team.members || [])
    .map((m) => (typeof m === "string" ? m : m.login))
    .filter(Boolean)
    .map((l) => String(l).toLowerCase());
}

function findTeamByLogin(teams, login) {
  const target = String(login).toLowerCase();
  return teams.find((t) => teamMemberLogins(t).includes(target));
}

module.exports = {
  OWNER,
  REPO,
  DEFAULT_BRANCH,
  github,
  getUser,
  getUserEmails,
  userEmails,
  requireEnv,
  slugify,
  readTeams,
  commitFiles,
  inviteCollaborator,
  isCollaborator,
  teamMemberLogins,
  findTeamByLogin,
};
