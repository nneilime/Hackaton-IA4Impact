import re, sys
src, sortie = sys.argv[1:3]
s = open(src).read()
corps = s[s.index('<body>') + 6:s.index('</body>')]
corps = corps.replace('<script type="module" src="/app.js"></script>', '<script type="module" src="serveur-local.js"></script>\n  <script type="module" src="app.js"></script>')
assert 'serveur-local.js' in corps
corps = corps.replace('<a class="evitement" href="#contenu">Aller au contenu</a>', '<a class="evitement" href="#contenu">Aller au contenu</a>\n  <p class="prototype">Prototype non officiel · données fictives du kit BâtIA</p>', 1)
assert 'class="prototype"' in corps
tete = """<title>Assise</title>
<link rel="stylesheet" href="vendor/fonts/polices.css">
<link rel="stylesheet" href="style.css">
<style>
  .entete { top: env(safe-area-inset-top, 0px); }
  .prototype { margin: 0; padding: 4px 16px; font: 500 12px/1.4 'Source Sans 3', system-ui, sans-serif; color: var(--encre); background: var(--fond); opacity: .72; text-align: center; }
</style>
"""
open(sortie, 'w').write(tete + corps.strip() + '\n')
