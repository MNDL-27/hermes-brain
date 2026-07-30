(function() {
  const MIN_RECONNECT_MS = 500;
  const MAX_RECONNECT_MS = 30000;
  let ws = null;
  let reconnectDelay = MIN_RECONNECT_MS;
  function sessionKey() {
    try { return window.sessionStorage.getItem('brainstorm-session-key'); } catch (e) { return null; }
  }
  function connect() {
    const key = sessionKey();
    ws = new WebSocket('ws://' + window.location.host + (key ? '/?key=' + encodeURIComponent(key) : ''));
    ws.onclose = () => {
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_MS);
    };
    ws.onopen = () => { reconnectDelay = MIN_RECONNECT_MS; };
  }
  connect();
})();
