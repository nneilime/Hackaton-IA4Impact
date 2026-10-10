"""The critical journeys in the browser with the real model (OpenAI key in .env):
uv run pytest tests/e2e -m live. The model's wording varies: these check the cards, the
buttons and the server state, which must hold whatever it says."""

import re

import pytest
from helpers import login, shot
from playwright.sync_api import expect

pytestmark = pytest.mark.live
SLOW = 60_000  # ms: a model answer with tool calls


def compass(page):
    return page.get_by_role("dialog", name="Compass, assistant bancaire")


def ask(page, text):
    """Writes to Compass once it is free (greeting or previous answer done)."""
    sheet = compass(page)
    if not sheet.count():
        page.get_by_role("button", name=re.compile("Écrire à Compass")).first.click()
    expect(sheet.get_by_text("En ligne", exact=True)).to_be_visible(timeout=SLOW)
    sheet.get_by_label("Votre message à Compass").fill(text)
    send = sheet.get_by_role("button", name="Envoyer")
    expect(send).to_be_visible(timeout=SLOW)  # not « Arrêter la réponse »
    expect(send).to_be_enabled()
    send.click()


def wait_answer(page):
    expect(compass(page).get_by_role("button", name="Envoyer")).to_be_visible(timeout=SLOW)


def test_journey_b_visitor_to_customer_and_back(page):
    page.goto("/")
    ask(page, "Quel est le solde de mon compte ?")
    card = compass(page).get_by_role("article", name="Connexion requise")
    expect(card).to_be_visible(timeout=SLOW)
    expect(compass(page)).not_to_contain_text("1 245")
    shot(page, "live-visitor-login-card")
    card.get_by_role("button", name="Connexion démo").click()
    dialog = page.get_by_role("dialog", name="Connexion démo")
    dialog.get_by_label("Code de démonstration").fill("compass")
    dialog.get_by_role("button", name="Se connecter (démo)").click()
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    # French grouping uses (narrow) no-break spaces on screen.
    screen_balance = page.locator("#main a[href='/comptes?account=acc_cc']").inner_text().replace("\u202f", " ").replace("\xa0", " ")
    page.get_by_role("button", name="Écrire à Compass, votre assistant bancaire").click()
    ask(page, "Quel est mon solde ?")
    balances = compass(page).get_by_role("article", name="Vos soldes")
    expect(balances).to_contain_text("1 245,80", timeout=SLOW)
    assert "1 245,80" in screen_balance  # the assistant and the screen agree
    wait_answer(page)
    shot(page, "live-customer-balance")
    compass(page).get_by_role("button", name="Fermer Compass").click()
    page.goto("/profil")
    page.get_by_role("button", name="Se déconnecter").click()
    expect(page.get_by_role("heading", name="Comment pouvons-nous vous aider ?")).to_be_visible()
    ask(page, "Quel est mon solde ?")
    expect(compass(page).get_by_role("article", name="Connexion requise")).to_be_visible(timeout=SLOW)
    expect(compass(page)).not_to_contain_text("1 245")


def test_journey_c_lost_card_locked_with_the_confirm_button(page):
    page.goto("/")
    login(page)
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    ask(page, "J'ai perdu ma carte bancaire, je pense l'avoir égarée. Verrouillez-la temporairement.")
    confirm = compass(page).get_by_role("article", name=re.compile("Action à confirmer"))
    expect(confirm).to_be_visible(timeout=SLOW)
    expect(confirm).to_contain_text("Verrouillage temporaire")
    wait_answer(page)
    shot(page, "live-confirm-card")
    # Not done before the yes.
    assert page.evaluate("fetch('/api/customer').then(r => r.json()).then(d => d.cards[0].status)") == "ACTIVE"
    confirm.get_by_role("button", name="Confirmer").click()
    expect(page.get_by_text("Carte verrouillée temporairement")).to_be_visible(timeout=SLOW)
    assert page.evaluate("fetch('/api/customer').then(r => r.json()).then(d => d.cards[0].status)") == "LOCKED"
    page.reload()
    expect(page.get_by_text("Carte verrouillée temporairement")).to_be_visible()
    shot(page, "live-card-locked-after-reload")


def test_journey_d_unknown_payment_and_handoff(page):
    page.goto("/")
    login(page)
    expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
    ask(page, "Je vois un paiement de 89 euros que je ne reconnais pas.")
    found = compass(page).get_by_role("article", name="Opérations trouvées")
    expect(found).to_contain_text("Paiement inconnu", timeout=SLOW)
    expect(found).to_contain_text("CB PAIEMENT EN LIGNE REF 4471-XK")
    wait_answer(page)
    ask(page, "Je voudrais parler à un conseiller.")
    confirm = compass(page).get_by_role("article", name=re.compile("Action à confirmer"))
    expect(confirm).to_be_visible(timeout=SLOW)
    wait_answer(page)
    shot(page, "live-handoff-review")
    confirm.get_by_role("button", name="Confirmer").click()
    expect(confirm).to_contain_text("Confirmé", timeout=SLOW)
    compass(page).get_by_role("button", name="Fermer Compass").click()
    page.goto("/demarches")
    expect(page.locator("#main")).to_contain_text("Transmise (simulation)")
    shot(page, "live-demarches")


def test_journey_a_visitor_advisor_request(page):
    page.goto("/")
    page.get_by_role("button", name="Je voudrais parler à un conseiller.").click()
    confirm = compass(page).get_by_role("article", name=re.compile("Action à confirmer"))
    expect(confirm).to_be_visible(timeout=SLOW)
    expect(confirm).to_contain_text("aucun conseiller réel")
    wait_answer(page)
    confirm.get_by_role("button", name="Confirmer").click()
    expect(confirm).to_contain_text("Confirmé", timeout=SLOW)
    compass(page).get_by_role("button", name="Fermer Compass").click()
    expect(page.get_by_role("heading", name="Vos demandes de démonstration")).to_be_visible()
    expect(page.locator("#main")).to_contain_text("Demande de démonstration enregistrée")
    shot(page, "live-visitor-request-saved")
    page.goto("/demarches")  # still a private page
    expect(page.get_by_role("heading", name="Connexion requise")).to_be_visible()
