"use strict";

// Minifie le front statique (HTML, CSS, JS) dans team-app/dist.
// Les noms de fichiers sont conservés pour ne pas réécrire les références.

const fs = require("fs");
const path = require("path");
const esbuild = require("esbuild");
const CleanCSS = require("clean-css");
const { minify } = require("html-minifier-terser");

const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "front");
const OUT = path.join(ROOT, "dist");

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(from, to);
    else fs.copyFileSync(from, to);
  }
}

async function main() {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  for (const file of ["app.js", "config.js"]) {
    await esbuild.build({
      entryPoints: [path.join(SRC, file)],
      outfile: path.join(OUT, file),
      bundle: false,
      minify: true,
      legalComments: "none",
      target: ["es2018"],
    });
  }

  const css = fs.readFileSync(path.join(SRC, "style.css"), "utf8");
  const minCss = new CleanCSS({ level: 2 }).minify(css);
  if (minCss.errors && minCss.errors.length) throw new Error(minCss.errors.join("\n"));
  fs.writeFileSync(path.join(OUT, "style.css"), minCss.styles);

  copyDir(path.join(SRC, "assets"), path.join(OUT, "assets"));
  copyDir(path.join(SRC, "data"), path.join(OUT, "data"));

  const html = fs.readFileSync(path.join(SRC, "index.html"), "utf8");
  const minHtml = await minify(html, {
    collapseWhitespace: true,
    removeComments: true,
    removeRedundantAttributes: true,
    keepClosingSlash: true,
    caseSensitive: true,
  });
  fs.writeFileSync(path.join(OUT, "index.html"), minHtml);

  console.log("Build front -> " + path.relative(ROOT, OUT));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
