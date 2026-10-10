(function () {
  var compte = null;
  try { compte = JSON.parse(localStorage.getItem('foraine.compte')); } catch (e) {}
  if (!compte || !compte.nom) location.replace('/connexion.html?suite=' + encodeURIComponent(location.pathname + location.search + location.hash));
})();
