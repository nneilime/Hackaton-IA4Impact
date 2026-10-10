from pathlib import Path
import tomllib


def test_un_seul_point_entree_streamlit() -> None:
    """Un dossier app/pages créerait une navigation Streamlit concurrente et vide."""
    racine = Path(__file__).parent.parent
    assert not (racine / "app" / "pages").exists()
    assert (racine / "app" / "views" / "preparation.py").is_file()
    assert (racine / "app" / "views" / "jour_j.py").is_file()
    assert (racine / "app" / "views" / "rejeu.py").is_file()


def test_theme_clair_force_des_contrastes_stables() -> None:
    racine = Path(__file__).parent.parent
    config = tomllib.loads(
        (racine / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    )
    assert config["theme"]["base"] == "light"
    assert config["theme"]["backgroundColor"] != config["theme"]["textColor"]
    assert config["theme"]["secondaryBackgroundColor"] != config["theme"]["textColor"]
    assert config["client"]["showSidebarNavigation"] is False


def test_selection_texte_garde_un_contraste_eleve() -> None:
    racine = Path(__file__).parent.parent
    css = (racine / "app" / "styles" / "theme.py").read_text(encoding="utf-8")

    assert "*::selection" in css
    assert "background: #004A92 !important" in css
    assert "color: #FFFFFF !important" in css
    assert "-webkit-text-fill-color: #FFFFFF !important" in css
