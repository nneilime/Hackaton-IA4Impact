"""Découpe les trois extraits du fond en morceaux de moins de 14 Mo (limite d'un fichier publié : 15 Mo)."""
import json, os, subprocess, sys
PM, FOND, SORTIE = sys.argv[1], sys.argv[2], sys.argv[3]
LIMITE = 11_500_000
SOURCES = [('france-z0-8', (-6.2, 41.0, 10.2, 51.6), 0, 8),
           ('sud-ouest-z9-11', (-2.3, 42.4, 4.5, 45.95), 9, 11),
           ('toulouse-z12-14', (0.95, 43.33, 1.9, 43.95), 12, 14)]
morceaux = []
def extraire(src, b, zmin, zmax):
    nom = f"z{zmin}-{zmax}_{b[0]:.3f}_{b[1]:.3f}_{b[2]:.3f}_{b[3]:.3f}.pmtiles".replace('-', 'm').replace('zm', 'z-').replace('z', 'z', 1)
    nom = f"m{len(morceaux)+len(pile):02d}-{zmin}-{zmax}.pmtiles"
    chemin = os.path.join(SORTIE, nom)
    subprocess.run([PM, 'extract', os.path.join(FOND, src + '.pmtiles'), chemin, '--bbox=%f,%f,%f,%f' % b,
                    '--minzoom=%d' % zmin, '--maxzoom=%d' % zmax], check=True, capture_output=True)
    return chemin, os.path.getsize(chemin)
pile = [(s, b, a, z) for s, b, a, z in SOURCES]
n = 0
while pile:
    src, b, zmin, zmax = pile.pop(0)
    n += 1
    chemin, taille = extraire(src, b, zmin, zmax)
    if taille <= LIMITE:
        final = os.path.join(SORTIE, f"fond-{len(morceaux):02d}.pmtiles")
        os.replace(chemin, final)
        morceaux.append({'fichier': 'fond/' + os.path.basename(final), 'min': zmin, 'max': zmax, 'bbox': [round(v, 4) for v in b], 'octets': taille})
        print(f"garde  z{zmin}-{zmax} {b} {taille/1e6:.1f} Mo", flush=True)
        continue
    os.remove(chemin)
    print(f"coupe  z{zmin}-{zmax} {b} {taille/1e6:.1f} Mo", flush=True)
    if zmin < zmax:
        pile[:0] = [(src, b, zmin, zmax - 1), (src, b, zmax, zmax)]
    else:
        w, s, e, nn = b
        if (e - w) >= (nn - s) * 1.3:
            m = (w + e) / 2; pile[:0] = [(src, (w, s, m, nn), zmin, zmax), (src, (m, s, e, nn), zmin, zmax)]
        else:
            m = (s + nn) / 2; pile[:0] = [(src, (w, s, e, m), zmin, zmax), (src, (w, m, e, nn), zmin, zmax)]
json.dump(morceaux, open(os.path.join(SORTIE, 'morceaux.json'), 'w'), indent=1)
print(len(morceaux), 'morceaux,', round(sum(m['octets'] for m in morceaux) / 1e6, 1), 'Mo')
