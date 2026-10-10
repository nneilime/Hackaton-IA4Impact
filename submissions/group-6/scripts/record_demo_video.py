"""Script d'enregistrement vidéo automatisé pour la démo du Copilote Enedis (Fiche C).

Génère une vidéo haute résolution (1280x720) de moins de 2 minutes (demo.mp4)
suivant rigoureusement le scénario imposé sur CRISE_024.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright


def inject_banner_script(page):
    page.evaluate(
        """
        () => {
            if (!document.getElementById('demo-banner')) {
                const banner = document.createElement('div');
                banner.id = 'demo-banner';
                banner.style.position = 'fixed';
                banner.style.bottom = '22px';
                banner.style.left = '50%';
                banner.style.transform = 'translateX(-50%)';
                banner.style.background = 'rgba(15, 23, 42, 0.92)';
                banner.style.color = '#ffffff';
                banner.style.padding = '10px 24px';
                banner.style.borderRadius = '30px';
                banner.style.fontFamily = 'system-ui, -apple-system, Roboto, sans-serif';
                banner.style.fontSize = '15px';
                banner.style.fontWeight = '600';
                banner.style.letterSpacing = '0.2px';
                banner.style.boxShadow = '0 12px 30px rgba(0, 0, 0, 0.35)';
                banner.style.zIndex = '999999';
                banner.style.border = '1px solid rgba(59, 130, 246, 0.4)';
                banner.style.backdropFilter = 'blur(8px)';
                banner.style.transition = 'all 0.3s ease';
                banner.innerText = 'Copilote de Crise Enedis · Démonstration opérationnelle';
                document.body.appendChild(banner);
            }
        }
        """
    )


def update_banner(page, text: str):
    page.evaluate(
        f"""
        () => {{
            const b = document.getElementById('demo-banner');
            if (b) {{
                b.style.opacity = '0';
                setTimeout(() => {{
                    b.innerText = {repr(text)};
                    b.style.opacity = '1';
                }}, 200);
            }}
        }}
        """
    )


def record_demo(output_video_path: str = "demo.mp4"):
    project_dir = Path(__file__).resolve().parent.parent
    temp_video_dir = project_dir / "outputs" / "temp_recordings"
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    print("=== Démarrage de l'enregistrement de la démo (Fiche C) ===")
    start_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,720",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(temp_video_dir),
            record_video_size={"width": 1280, "height": 720},
        )

        page = context.new_page()

        # ----------------------------------------------------------------- 1. Accueil & Chargement
        print("[00:00] Chargement de la Salle de crise express...")
        page.goto("http://localhost:8524/Salle_de_crise_express", timeout=60000)
        page.wait_for_timeout(4000)
        inject_banner_script(page)
        update_banner(page, "Salle de crise express · L'outil recommande, le responsable décide")
        page.wait_for_timeout(4000)

        # ----------------------------------------------------------------- 2. Sélection CRISE_024 & Indicateurs
        print("[00:12] Sélection de CRISE_024 & Focus Indicateurs...")
        update_banner(page, "Sélection de la CRISE_024 · 212 incidents, 63 équipes mobilisées")
        sidebar = page.locator('[data-testid="stSidebar"]')
        comboboxes = sidebar.locator('[data-baseweb="select"]').all()
        if comboboxes:
            comboboxes[0].click()
            page.wait_for_timeout(800)
            page.keyboard.type("CRISE_024")
            page.wait_for_timeout(800)
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

        inject_banner_script(page)
        update_banner(
            page,
            "Indicateurs clés · WSPT −4.9 % vs R2 (−14.4 % vs R1) | Attente sensible : 2.7h vs 5.5h (R2)",
        )
        page.wait_for_timeout(7000)

        # ----------------------------------------------------------------- 3. Courbe des clients coupés
        print("[00:32] Défilement vers la courbe des clients coupés...")
        page.mouse.wheel(0, 450)
        page.wait_for_timeout(1000)
        update_banner(
            page,
            "Courbe de crise · Rétablissement accéléré à H+4 : 19 % de foyers réalimentés vs 10 % (R2)",
        )
        page.wait_for_timeout(8000)

        # Défilement équipes dans le temps
        page.mouse.wheel(0, 350)
        page.wait_for_timeout(1000)
        update_banner(page, "Engagement des équipes · Respect strict de l'amplitude max (0 dépassement)")
        page.wait_for_timeout(6000)

        # ----------------------------------------------------------------- 4. Carte opérationnelle
        print("[00:50] Défilement vers la Carte de la crise...")
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(1500)
        update_banner(
            page,
            "Carte opérationnelle (H+6) · Rouge = en attente, Violet = client sensible prioritaire",
        )
        page.wait_for_timeout(7000)

        # Curseur temporel H+6 -> H+20
        print("[01:00] Glissement du curseur temporel vers H+20...")
        update_banner(page, "Progression temporelle H+6 → H+20 · Rétablissement des sites prioritaires")
        slider_container = (
            page.locator('div:has-text("Heure depuis le début de la crise")')
            .locator('[role="slider"]')
            .first
        )
        if slider_container.count() > 0:
            slider_container.focus()
            for _ in range(28):  # passe à ~H+19 / H+20
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(100)
            page.wait_for_timeout(6000)

        # ----------------------------------------------------------------- 5. Décisions expliquées & Arbitrage
        print("[01:15] Défilement vers les Décisions expliquées...")
        page.mouse.wheel(0, 850)
        page.wait_for_timeout(1500)
        update_banner(page, "Décisions expliquées · Justification transparente et score de confiance")
        page.wait_for_timeout(5000)

        # Filtrer sur les décisions à discuter
        print("[01:22] Filtrage : seulement les décisions à discuter...")
        radio_opt = page.locator('text="seulement les décisions à discuter"')
        if radio_opt.count() > 0:
            radio_opt.first.click()
            page.wait_for_timeout(3000)
            update_banner(
                page,
                "Arbitrage humain · Décision signalée ⚠️ à discuter (arbitrage serré)",
            )
            page.wait_for_timeout(5000)

        # Refuser cette affectation
        print("[01:29] Refus d'une affectation...")
        refuse_btn = page.locator('button:has-text("Refuser cette affectation")')
        if refuse_btn.count() > 0:
            refuse_btn.first.click()
            page.wait_for_timeout(4000)
            update_banner(
                page,
                "Arbitrage pris en compte · Rejeu instantané : impact chiffré (+110 clients·heures)",
            )
            page.wait_for_timeout(7000)

        # ----------------------------------------------------------------- 6. Stress test routes coupées
        print("[01:38] Remontée & Activation Stress test routes coupées...")
        page.mouse.wheel(0, -2200)
        page.wait_for_timeout(1000)
        update_banner(page, "Stress test · Routes coupées en montagne (vitesse divisée par 3)")
        routes_cb = sidebar.locator('text="Routes coupées en montagne"')
        if routes_cb.count() > 0:
            routes_cb.first.click()
            page.wait_for_timeout(6000)
            update_banner(
                page,
                "Résilience éprouvée · WSPT reste optimal (207k vs 239k R1, sensibles < 3h)",
            )
            page.wait_for_timeout(7000)

        # ----------------------------------------------------------------- 7. Conclusion
        print("[01:48] Conclusion...")
        update_banner(page, "Copilote Enedis · 100 % CPU, souverain, explicable et centré sur l'humain")
        page.wait_for_timeout(5000)

        # Finalisation du navigateur et capture de la vidéo
        context.close()
        video_path = page.video.path()
        browser.close()

    elapsed = time.time() - start_time
    print(f"Enregistrement brut terminé en {elapsed:.1f}s. Fichier source : {video_path}")

    # Conversion ffmpeg vers MP4
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    final_output = project_dir / output_video_path

    print(f"Transcodage avec ffmpeg ({ffmpeg_exe}) vers {final_output}...")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-r",
        "30",
        str(final_output),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Erreur ffmpeg:", res.stderr)
        raise RuntimeError(f"Échec transcodage ffmpeg: {res.stderr}")

    size_mb = os.path.getsize(final_output) / (1024 * 1024)
    print(f"Vidéo finale générée avec succès : {final_output}")
    print(f"Taille du fichier : {size_mb:.2f} Mo")

    # Nettoyage
    shutil.rmtree(temp_video_dir, ignore_errors=True)
    return str(final_output)


if __name__ == "__main__":
    record_demo()
