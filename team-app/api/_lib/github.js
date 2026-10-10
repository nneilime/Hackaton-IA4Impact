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
    const detail = typeof data === "string" ? data.split("\n")[0] : (data && data.message) || "";
    const err = new Error(`Lecture de teams.json impossible (${status}${detail ? " " + detail : ""})`);
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
  if (login && OWNER && login.toLowerCase() === String(OWNER).toLowerCase()) return true;
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

function csvCell(value) {
  const s = value == null ? "" : String(value);
  return /[",\n\r;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
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

const PARTICIPANTS_HEADER = ["email_hash", "email_enc", "login", "team_name"];

// Registre des participants : source de vérité des hashes d'emails.
// Les emails ne sont stockés que sous forme hashée + chiffrée.
async function readParticipants() {
  const { status, data } = await github(
    `/repos/${OWNER}/${REPO}/contents/participants.csv?ref=${encodeURIComponent(DEFAULT_BRANCH)}`
  );
  if (status === 404) return { rows: [] };
  if (status !== 200) {
    const detail = typeof data === "string" ? data.split("\n")[0] : (data && data.message) || "";
    const err = new Error(`Lecture de participants.csv impossible (${status}${detail ? " " + detail : ""})`);
    err.statusCode = 502;
    throw err;
  }
  const decoded = Buffer.from(data.content, "base64").toString("utf8");
  const parsed = parseCsv(decoded);
  if (!parsed.length) return { rows: [] };
  const header = parsed[0].map((h) => String(h).trim());
  const rows = parsed
    .slice(1)
    .map((cells) => {
      const obj = {};
      header.forEach((h, i) => {
        obj[h] = cells[i] != null ? cells[i] : "";
      });
      return {
        email_hash: (obj.email_hash || "").trim(),
        email_enc: obj.email_enc || "",
        login: (obj.login || "").trim(),
        team_name: obj.team_name || "",
      };
    })
    .filter((r) => r.email_hash || r.login);
  return { rows };
}

function serializeParticipants(rows) {
  const lines = (rows || []).map((r) =>
    [
      csvCell(r.email_hash || ""),
      csvCell(r.email_enc || ""),
      csvCell(r.login || ""),
      csvCell(r.team_name || ""),
    ].join(",")
  );
  return [PARTICIPANTS_HEADER.join(","), ...lines].join("\n") + "\n";
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
  readParticipants,
  serializeParticipants,
  commitFiles,
  inviteCollaborator,
  isCollaborator,
  teamMemberLogins,
  findTeamByLogin,
  csvCell,
}
