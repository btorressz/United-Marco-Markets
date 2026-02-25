const WS = (() => {
  let socket = null;
  let reconnectAttempts = 0;
  let maxReconnect = 10;
  let reconnectTimer = null;
  let handlers = {};
  let messageQueue = [];
  let connected = false;

  function getWsUrl() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}/ws/live`;
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      socket = new WebSocket(getWsUrl());
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err);
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      console.log('[WS] Connected');
      reconnectAttempts = 0;
      connected = true;
      dispatch('connectionChange', true);
      flushQueue();
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        dispatch('message', data);

        if (data.type) {
          dispatch(data.type, data);
        }
      } catch (err) {
        console.warn('[WS] Failed to parse message:', err);
      }
    };

    socket.onclose = () => {
      console.log('[WS] Disconnected');
      connected = false;
      dispatch('connectionChange', false);
      scheduleReconnect();
    };

    socket.onerror = (err) => {
      console.error('[WS] Error:', err);
    };
  }

  function scheduleReconnect() {
    if (reconnectAttempts >= maxReconnect) {
      console.warn('[WS] Max reconnect attempts reached');
      return;
    }
    if (document.hidden) {
      console.log('[WS] Tab hidden, deferring reconnect');
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
    reconnectAttempts++;
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, delay);
  }

  function dispatch(type, data) {
    const fns = handlers[type];
    if (fns && fns.length > 0) {
      fns.forEach(fn => {
        try { fn(data); } catch (e) { console.error('[WS] Handler error:', e); }
      });
    } else if (type === 'message') {
      messageQueue.push(data);
      if (messageQueue.length > 100) messageQueue.shift();
    }
  }

  function flushQueue() {
    const queued = messageQueue.splice(0);
    queued.forEach(msg => dispatch('message', msg));
  }

  function on(type, fn) {
    if (!handlers[type]) handlers[type] = [];
    handlers[type].push(fn);
  }

  function off(type, fn) {
    if (!handlers[type]) return;
    handlers[type] = handlers[type].filter(f => f !== fn);
  }

  function send(data) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }

  function isConnected() {
    return connected;
  }

  return { connect, on, off, send, isConnected };
})();
