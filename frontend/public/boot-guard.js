(function () {
  function fail() { var block = document.getElementById('boot-failed'); if (!block) return; block.hidden = false; var pending = document.getElementById('boot-pending'); if (pending) pending.hidden = true; }
  var timer = setTimeout(fail, 15000);
  function resourceError(event) { if (event.target instanceof HTMLScriptElement) fail(); }
  window.addEventListener('error', resourceError, true);
  window.addEventListener('lims:mounted', function () { clearTimeout(timer); window.removeEventListener('error', resourceError, true); }, { once: true });
  document.getElementById('boot-retry').addEventListener('click', function () { window.location.reload(); });
})();
