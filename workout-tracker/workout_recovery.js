// Drafts stay on this device until the server confirms the matching values saved.
(() => {
  const prefix = 'workout-draft-v1:';
  window.workoutDrafts = {
    put(key, value) {
      try {
        localStorage.setItem(prefix + key, JSON.stringify({value, revision: crypto.randomUUID()}));
      } catch (_) {
        document.querySelector('.workout-draft-status')?.replaceChildren(
          document.createTextNode('Device draft storage unavailable. Save before locking.'));
      }
    },
    read(scope) {
      const result = {};
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (!key.startsWith(prefix + scope)) continue;
          try {
            const entry = JSON.parse(localStorage.getItem(key));
            if (entry && typeof entry.revision === 'string') result[key.slice(prefix.length)] = entry;
          } catch (_) { /* Ignore a malformed draft without deleting it. */ }
        }
      } catch (_) { /* Saving to Turso remains available without local storage. */ }
      return result;
    },
    acknowledge(snapshot) {
      for (const [key, entry] of Object.entries(snapshot)) {
        try {
          const current = JSON.parse(localStorage.getItem(prefix + key));
          if (current?.revision === entry.revision) localStorage.removeItem(prefix + key);
        } catch (_) { /* Retaining a draft is safer than clearing a newer edit. */ }
      }
    },
  };

  // iOS may leave a socket appearing connected after suspending the page.
  // Reopen the transport on return, retaining NiceGUI's page and replay state.
  let hiddenAt = null;
  function resume() {
    if (!location.pathname.startsWith('/session/') || document.hidden) return;
    const wasSuspended = hiddenAt !== null && Date.now() - hiddenAt > 1000;
    hiddenAt = null;
    const socket = window.socket;
    if (!socket) return;
    if (wasSuspended && socket.connected) {
      // Close the transport, not socket.disconnect(): automatic reconnection
      // and NiceGUI's reconnect_attempt callback must remain enabled.
      socket.io.engine?.close();
    } else if (!socket.connected) {
      socket.connect();
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) hiddenAt = Date.now();
    else resume();
  });
  window.addEventListener('pageshow', resume);
  window.addEventListener('online', resume);
})();
