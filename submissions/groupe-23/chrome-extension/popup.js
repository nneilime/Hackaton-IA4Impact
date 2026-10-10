const status = document.querySelector('#status');
const launchButton = document.querySelector('#launch');
const formUrl = 'https://www.caisse-epargne.fr/formulaire/contact/auth-generic?form=reclam&bank=13135';

async function openAssistant() {
  launchButton.disabled = true;
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    const demoUrl = chrome.runtime.getURL('demo.html');
    const isDemo = tab?.url === demoUrl;
    const isBankPage = CE.siteAllowed(tab?.url);

    if (!tab?.id || (!isDemo && !isBankPage)) {
      await chrome.tabs.create({url: formUrl});
      window.close();
      return;
    }

    if (isDemo) {
      const result = await chrome.runtime.sendMessage({type: 'ce-show', demoTabId: tab.id});
      if (!result?.ok) throw new Error('Rechargez la démonstration puis réessayez.');
    } else {
      await chrome.scripting.executeScript({
        target: {tabId: tab.id},
        files: ['shared.js', 'mortgage-contract.js', 'adapter.js', 'mortgage-adapter.js', 'panel-view.js', 'markdown.js', 'panel.js']
      });
    }
    window.close();
  } catch (error) {
    status.textContent = error.message || 'Impossible d’afficher le panneau sur cette page.';
  } finally {
    launchButton.disabled = false;
  }
}

launchButton.onclick = openAssistant;
