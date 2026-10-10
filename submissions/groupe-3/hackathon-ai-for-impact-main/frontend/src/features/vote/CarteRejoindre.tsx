import { Smartphone, Wifi, WifiOff } from 'lucide-react'
import QrCodeVote from './QrCodeVote'
import type { AdresseVote } from './useUrlVote'

interface CarteRejoindreProps {
  code: string
  adresse: AdresseVote
}

/** Colonne gauche de l'écran projeté : QR code, code du vote et adresse en clair. */
export default function CarteRejoindre({ code, adresse }: CarteRejoindreProps) {
  return (
    <div className="card border-2 border-secondary bg-base-100 shadow-[6px_6px_0_0] shadow-secondary">
      <div className="card-body items-center gap-4 p-5 text-center lg:p-6">
        <h2 id="titre-rejoindre" className="card-title text-2xl font-extrabold tracking-tight lg:text-3xl">
          <Smartphone className="size-7 shrink-0" aria-hidden="true" />
          Scannez pour voter
        </h2>

        {adresse.etat === 'calcul' && <div className="skeleton aspect-square w-full max-w-80" />}
        {adresse.etat === 'prete' && (
          <QrCodeVote
            url={adresse.url}
            className="aspect-square w-full max-w-80 rounded-field border-4 border-secondary"
          />
        )}
        {adresse.etat === 'sans-ip' && (
          <div className="grid aspect-square w-full max-w-80 place-items-center rounded-field border-4 border-dashed border-base-300">
            <WifiOff className="size-16 opacity-40" aria-hidden="true" />
          </div>
        )}

        <div className="grid gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide">Code du vote</p>
          <p
            className="text-5xl font-extrabold tabular-nums tracking-[0.2em]"
            aria-label={`Code du vote : ${code.split('').join(' ')}`}
          >
            {code}
          </p>
        </div>

        {adresse.etat === 'prete' && (
          <div className="grid gap-1">
            <p className="text-base">Pas d’appareil photo ? Tapez l’adresse :</p>
            <p className="font-mono text-lg font-bold break-all">{adresse.url}</p>
            <p className="flex items-center justify-center gap-2 text-sm font-semibold opacity-80">
              <Wifi className="size-4 shrink-0" aria-hidden="true" />
              Les téléphones doivent être sur le même Wi-Fi que cet ordinateur.
            </p>
          </div>
        )}
        {adresse.etat === 'sans-ip' && (
          <div role="alert" className="alert alert-warning alert-vertical text-left">
            <WifiOff className="size-6 shrink-0" aria-hidden="true" />
            <div className="grid gap-1">
              <h3 className="font-bold">Adresse réseau introuvable</h3>
              <p className="text-sm">
                Les téléphones doivent être sur le même Wi-Fi ; ouvrez le site via l’adresse « Network » affichée
                par Vite.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
