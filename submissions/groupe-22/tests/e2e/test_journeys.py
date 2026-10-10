"""The page in a real browser, without the model: public home, private pages, the
Connexion démo, the bank's screens, the card lock, logout, layouts, keyboard."""

import json
import re

import pytest
from helpers import login, shot
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect

PRIVATE_PATHS = ["/comptes", "/operations", "/cartes", "/demarches", "/profil", "/operations?tx=tx_inconnu"]


def leaks(page):
    return page.evaluate("window.__leaks")


def test_public_home_shows_no_private_data(page):
    page.goto("/")
    expect(page.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    expect(page.get_by_text("Vous avez une question bancaire ? Compass vous accompagne.")).to_be_visible()
    expect(page.get_by_role("button", name="Connexion démo").first).to_be_visible()
    for question in ["Je souhaite simuler un crédit.", "J'ai oublié mon mot de passe.", "Je veux faire une réclamation.", "Je voudrais parler à un conseiller.", "Comment ouvrir un compte ?"]:
        expect(page.get_by_role("button", name=question)).to_be_visible()
    expect(page.locator("#bottom-nav")).to_have_count(0)  # the bank's menu: customers only
    expect(page.get_by_text("Prototype de démonstration", exact=False).first).to_be_visible()
    shot(page, "public-home-390")
    assert leaks(page) == []
    assert page.errors == []


@pytest.mark.parametrize("path", PRIVATE_PATHS)
def test_private_pages_are_closed_to_visitors(page, path):
    statuses = []
    page.on("response", lambda r: "/api/customer" in r.url and statuses.append(r.status))
    page.goto(path)
    expect(page.get_by_role("heading", name="Connexion requise")).to_be_visible()
    page.wait_for_timeout(300)
    assert leaks(page) == []  # not even for a frame
    assert all(s == 401 for s in statuses)
    page.reload()  # still closed after a reload
    expect(page.get_by_role("heading", name="Connexion requise")).to_be_visible()
    assert leaks(page) == []


def test_api_refuses_a_visitor_from_the_browser(page):
    page.goto("/")
    status = page.evaluate("fetch('/api/customer').then(r => r.status)")
    assert status == 401


def test_wrong_code_is_refused_then_login_opens_the_dashboard(page):
    page.goto("/")
    dialog = login(page, code="1234")
    expect(dialog.get_by_role("alert")).to_have_text("Code de démonstration incorrect.")
    expect(page.locator("#bottom-nav")).to_have_count(0)
    shot(page, "login-error")
    dialog.get_by_label("Code de démonstration").fill("compass")
    dialog.get_by_role("button", name="Se connecter (démo)").click()
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    expect(page.locator("#main")).to_contain_text("1 245,80")
    expect(page.locator("#main")).to_contain_text("8 650,00")
    expect(page.locator("#bottom-nav")).to_be_visible()
    shot(page, "dashboard-390")
    page.reload()  # the session holds
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    assert page.errors == []


def test_login_from_a_private_page_lands_on_it(page):
    page.goto("/cartes")
    page.get_by_role("button", name="Connexion démo").click()
    dialog = page.get_by_role("dialog", name="Connexion démo")
    dialog.get_by_label("Code de démonstration").fill("compass")
    dialog.get_by_role("button", name="Se connecter (démo)").click()
    expect(page.get_by_role("heading", name="Mes cartes")).to_be_visible()
    assert page.url.endswith("/cartes")


def test_screens_and_navigation(page):
    page.goto("/")
    login(page)
    nav = page.locator("#bottom-nav")
    nav.get_by_role("link", name="Comptes").click()
    expect(page.get_by_role("heading", name="Mes comptes")).to_be_visible()
    expect(page.locator("#main")).to_contain_text("1 245,80")
    page.get_by_role("tab", name="Livret A").click()
    expect(page.locator("#main")).to_contain_text("8 650,00")
    page.goto("/operations")
    page.get_by_label("Rechercher une opération").fill("netflix")
    expect(page.get_by_role("button", name=re.compile("^Netflix"))).to_have_count(2)
    page.get_by_label("Rechercher une opération").fill("")
    page.goto("/operations?tx=tx_inconnu")
    detail = page.get_by_role("dialog", name="Détail de l'opération")
    expect(detail).to_contain_text("CB PAIEMENT EN LIGNE REF 4471-XK")
    expect(detail).to_contain_text("89,00")
    page.goto("/operations?tx=does_not_exist")  # an unknown operation: just the list
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.goto("/demarches")
    expect(page.get_by_text("Aucune démarche pour l'instant")).to_be_visible()
    page.goto("/profil")
    expect(page.locator("#main").get_by_text("Camille Martin")).to_be_visible()
    assert page.errors == []


def test_card_lock_changes_the_server_state_and_persists(page):
    page.goto("/")
    login(page)
    page.goto("/cartes")
    page.get_by_role("button", name=re.compile("Verrouiller temporairement")).click()
    dialog = page.get_by_role("dialog", name="Verrouiller la carte ?")
    dialog.get_by_role("button", name="Annuler").click()  # cancel: nothing changes
    expect(page.get_by_text("Carte verrouillée temporairement")).to_have_count(0)
    page.get_by_role("button", name=re.compile("Verrouiller temporairement")).click()
    page.get_by_role("dialog", name="Verrouiller la carte ?").get_by_role("button", name="Verrouiller").click()
    expect(page.get_by_text("Carte verrouillée temporairement")).to_be_visible()
    shot(page, "card-locked")
    status = page.evaluate("fetch('/api/customer').then(r => r.json()).then(d => d.cards.find(c => c.id === 'card_visa').status)")
    assert status == "LOCKED"
    page.reload()
    expect(page.get_by_text("Carte verrouillée temporairement")).to_be_visible()
    page.get_by_role("button", name=re.compile("Déverrouiller la carte")).click()
    page.get_by_role("dialog", name="Déverrouiller la carte ?").get_by_role("button", name="Déverrouiller").click()
    expect(page.get_by_text("Carte verrouillée temporairement")).to_have_count(0)
    assert page.errors == []


def test_logout_revokes_access(page):
    page.goto("/")
    login(page)
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    old_cookie = next(c for c in page.context.cookies() if c["name"] == "compass_session")
    assert old_cookie["httpOnly"] and old_cookie["sameSite"] == "Lax"
    assert page.evaluate("document.cookie") == ""  # page scripts can't read the session
    page.goto("/profil")
    page.get_by_role("button", name="Se déconnecter").click()
    expect(page.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    expect(page.locator("#main")).not_to_contain_text("1 245,80")
    assert page.evaluate("fetch('/api/customer').then(r => r.status)") == 401
    # The old cookie, replayed: refused.
    page.context.add_cookies([old_cookie])
    assert page.evaluate("fetch('/api/customer').then(r => r.status)") == 401
    page.go_back()  # history: no private page comes back
    expect(page.get_by_role("heading", name=re.compile("Connexion requise|Comment pouvons-nous"))).to_be_visible()


def test_repeated_logins_and_logouts(page):
    page.goto("/")
    for profile, name in [("Camille Martin", "Camille"), ("Lucas Bernard", "Lucas"), ("Camille Martin", "Camille")]:
        login(page, profile=profile)
        expect(page.get_by_role("heading", name=f"Bonjour {name}")).to_be_visible()
        page.goto("/profil")
        page.get_by_role("button", name="Se déconnecter").click()
        expect(page.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    assert page.errors == []


def test_lucas_sees_his_own_data_only(page):
    page.goto("/")
    login(page, profile="Lucas Bernard")
    expect(page.get_by_role("heading", name="Bonjour Lucas")).to_be_visible()
    expect(page.locator("#main")).to_contain_text("3 120,40")
    expect(page.locator("#main")).not_to_contain_text("1 245,80")


@pytest.mark.parametrize("width", [375, 390, 430, 768, 1440])
def test_no_horizontal_overflow(browser, base_url, width):
    context = browser.new_context(base_url=base_url, viewport={"width": width, "height": 900})
    page = context.new_page()
    page.goto("/")
    expect(page.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    overflow = "document.documentElement.scrollWidth - window.innerWidth"
    assert page.evaluate(overflow) <= 0
    shot(page, f"public-{width}")
    login(page)
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    assert page.evaluate(overflow) <= 0
    shot(page, f"dashboard-{width}")
    for path in ["/cartes", "/operations", "/profil"]:
        page.goto(path)
        page.wait_for_load_state("networkidle")
        assert page.evaluate(overflow) <= 0, path
    context.close()


def test_keyboard_login_and_focus(page):
    page.goto("/")
    expect(page.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    header_button = page.get_by_role("button", name="Connexion démo").first
    header_button.focus()
    page.keyboard.press("Enter")
    dialog = page.get_by_role("dialog", name="Connexion démo")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Code de démonstration")).to_be_focused()
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(header_button).to_be_focused()  # focus back where it was
    page.keyboard.press("Enter")
    expect(dialog.get_by_label("Code de démonstration")).to_be_focused()
    page.keyboard.type("compass")
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()


def test_compass_opens_and_closes_for_a_visitor(page):
    """The sheet itself (no message sent): opens, says the visitor isn't logged in."""
    page.goto("/")
    page.get_by_role("button", name="Écrire à Compass").click()
    sheet = page.get_by_role("dialog", name="Compass, assistant bancaire")
    expect(sheet).to_be_visible()
    expect(sheet).to_contain_text("Compass n'a accès à aucun compte")
    expect(page.get_by_label("Votre message à Compass")).to_be_focused()
    sheet.get_by_role("button", name="Fermer Compass").click()
    expect(sheet).to_have_count(0)


def fake_chat(page):
    """/api/chat without OpenAI: « Bienvenue. », then « Réponse. » to each message, as
    Realtime events (the ones server.py relays)."""

    def answer(ws, n):
        item = f"item{n}"
        text = "Réponse." if n > 1 else "Bienvenue."
        for event in (
            {"type": "response.created", "response": {"id": f"resp{n}"}},
            {"type": "response.output_text.delta", "item_id": item, "delta": text},
            {"type": "response.output_text.done", "item_id": item, "text": text},
            {"type": "response.done", "response": {"status": "completed", "output": []}},
        ):
            ws.send(json.dumps(event))

    def handler(ws):
        turns = iter(range(1, 100))
        answer(ws, next(turns))  # the greeting
        ws.on_message(lambda message: json.loads(message).get("type") == "message" and answer(ws, next(turns)))

    page.route_web_socket(re.compile(r".*/api/chat.*"), handler)


def test_stars_asked_when_closing_compass_after_a_question(page):
    fake_chat(page)
    page.goto("/")
    before = page.evaluate("fetch('/api/ratings').then(r => r.json())")["count"]
    page.get_by_role("button", name="Écrire à Compass").click()
    sheet = page.get_by_role("dialog", name="Compass, assistant bancaire")
    sheet.get_by_role("button", name="Fermer Compass").click()  # nothing asked yet: closes
    expect(sheet).to_have_count(0)
    page.get_by_role("button", name="Écrire à Compass").click()
    expect(sheet.get_by_role("log")).to_contain_text("Bienvenue.")
    page.get_by_label("Votre message à Compass").fill("Bonjour")
    page.keyboard.press("Enter")
    expect(sheet.get_by_role("log")).to_contain_text("Réponse.")
    sheet.get_by_role("button", name="Fermer Compass").click()
    expect(sheet.get_by_role("heading", name="Votre avis")).to_be_focused()
    send = sheet.get_by_role("button", name="Envoyer")
    expect(send).to_be_disabled()
    sheet.get_by_label("4 étoiles sur 5").check(force=True)  # the radio is visually hidden
    shot(page, "rating")
    send.click()
    expect(sheet).to_have_count(0)
    expect(page.get_by_role("status").filter(has_text="Merci pour votre avis.")).to_be_visible()
    after = page.evaluate("fetch('/api/ratings').then(r => r.json())")
    assert after["count"] == before + 1
    # Rated: closing again doesn't ask again.
    page.get_by_role("button", name="Écrire à Compass").click()
    sheet.get_by_role("button", name="Fermer Compass").click()
    expect(sheet).to_have_count(0)
    assert page.errors == []


def test_stars_can_be_skipped_with_escape(page):
    fake_chat(page)
    page.goto("/")
    page.get_by_role("button", name="Écrire à Compass").click()
    sheet = page.get_by_role("dialog", name="Compass, assistant bancaire")
    expect(sheet.get_by_role("log")).to_contain_text("Bienvenue.")
    page.get_by_label("Votre message à Compass").fill("Bonjour")
    page.keyboard.press("Enter")
    expect(sheet.get_by_role("log")).to_contain_text("Réponse.")
    sheet.get_by_role("button", name="Nouvelle conversation").click()
    expect(sheet.get_by_role("heading", name="Votre avis")).to_be_visible()
    page.keyboard.press("Escape")  # « Passer »: then the new conversation
    expect(sheet.get_by_role("heading", name="Votre avis")).to_have_count(0)
    expect(sheet.get_by_role("log")).not_to_contain_text("Réponse.")  # a new conversation


def test_logout_in_another_tab_closes_this_one(page):
    page.goto("/")
    login(page)
    page.goto("/cartes")
    expect(page.get_by_role("heading", name="Mes cartes")).to_be_visible()
    other = page.context.new_page()
    other.goto("/profil")
    other.get_by_role("button", name="Se déconnecter").click()
    expect(other.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    other.close()
    page.bring_to_front()
    page.evaluate("window.dispatchEvent(new Event('focus'))")  # back on this tab
    expect(page.get_by_role("heading", name="Connexion requise")).to_be_visible()
    expect(page.locator("#main")).not_to_contain_text("4821")


def test_microphone_refused_offers_writing(browser, base_url):
    """The browser refuses the mic (as when the person says no): voice says so and
    offers the written chat. The refusal is made at the API the page calls."""
    context = browser.new_context(base_url=base_url, viewport={"width": 390, "height": 844})
    context.add_init_script(
        "navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError'))"
    )
    page = context.new_page()
    page.goto("/")
    page.get_by_role("button", name="Parler à Compass (conversation vocale)").click()
    call = page.get_by_label("Conversation vocale avec Compass")
    expect(call.get_by_role("alert")).to_contain_text("micro", timeout=15000)
    shot(page, "mic-denied")
    call.get_by_role("button", name="Continuer par écrit").click()
    expect(page.get_by_label("Votre message à Compass")).to_be_visible()
    context.close()


def test_demo_panel_reset_gives_a_fresh_sandbox(browser, base_url):
    context = browser.new_context(base_url=base_url, viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto("/")
    login(page)
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    page.evaluate("fetch('/api/cards/card_visa/lock', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})")
    page.reload()
    panel = page.get_by_role("complementary", name="Panneau de démonstration")
    expect(panel).to_contain_text("verrouillée")
    panel.get_by_role("button", name="Réinitialiser la démo").click()
    expect(panel).to_contain_text("Camille Martin")
    expect(panel).to_contain_text("Carte active")
    status = page.evaluate("fetch('/api/customer').then(r => r.json()).then(d => d.cards[0].status)")
    assert status == "ACTIVE"
    context.close()


AXE = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"


@pytest.mark.parametrize("path, customer", [("/", False), ("/cartes", False), ("/", True), ("/cartes", True), ("/operations", True), ("/profil", True)])
def test_accessibility_scan(page, path, customer):
    """axe-core (WCAG 2 A and AA rules) on the main screens: no serious or critical
    violation. Automated checks only: a screen reader pass is still needed."""
    page.goto("/")
    if customer:
        login(page)
        expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    page.goto(path)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)  # toasts and sheets settled
    try:
        page.add_script_tag(url=AXE)
    except PlaywrightError:
        pytest.skip("axe-core CDN unreachable")
    result = page.evaluate("axe.run(document, {runOnly: ['wcag2a', 'wcag2aa']})")
    serious = [
        f"{v['id']} ({v['impact']}): {v['help']} -> {[n['target'] for n in v['nodes']][:3]}"
        for v in result["violations"]
        if v["impact"] in ("serious", "critical")
    ]
    assert serious == [], "\n".join(serious)
