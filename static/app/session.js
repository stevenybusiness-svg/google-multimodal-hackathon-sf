window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core, render, media, documents } = window.MeetingAgent;
  const { dom, state, contracts, ensureSessionId, resetSessionId, sessionQuery } = core;

  function closeWs() {
    if (state.ws && state.ws.readyState !== WebSocket.CLOSED) {
      state.ws.close();
    }
    state.ws = null;
  }

  function handleWsMessage(message) {
    if (!message || !contracts.wsTypes.has(message.type)) return;
    if (message.type === 'done') {
      closeWs();
      return;
    }
    if (message.type === 'transcript') render.handleTranscriptMessage(message.data);
    if (message.type === 'interim') render.handleInterimMessage(message.data);
    if (message.type === 'action') render.handleActionMessage(message.data);
    if (message.type === 'sentiment') render.handleSentimentMessage(message.data);
    if (message.type === 'status') render.handleStatusMessage(message.data);
  }

  async function startMeeting() {
    if (state.starting || state.active) return;
    state.starting = true;
    dom.startBtn.disabled = true;
    render.setStartError('');
    render.resetMeetingState();
    ensureSessionId();
    render.showScreen('meeting');
    dom.statusText.textContent = 'Connecting...';

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    state.ws = new WebSocket(`${proto}//${location.host}/ws/audio${sessionQuery()}`);
    state.ws.binaryType = 'arraybuffer';

    await new Promise((resolve, reject) => {
      state.ws.onopen = resolve;
      state.ws.onerror = () => reject(new Error('Server unreachable'));
      state.ws.onclose = () => reject(new Error('Connection closed'));
    });

    dom.statusText.textContent = 'Listening...';
    state.ws.onerror = (event) => {
      console.error('WebSocket error', event);
      stopMeeting('disconnected');
    };
    state.ws.onclose = () => {
      if (state.active) stopMeeting('disconnected');
    };
    state.ws.onmessage = (event) => {
      try {
        handleWsMessage(JSON.parse(event.data));
      } catch (error) {
        console.warn('Ignored malformed server message', error);
      }
    };

    await media.startMedia();
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
      throw new Error('Connection lost during setup');
    }

    state.active = true;
    state.starting = false;
    dom.startBtn.disabled = false;
    await documents.loadDocumentWidget();
  }

  function stopMeeting(reason) {
    const wasActive = state.active;
    state.active = false;
    state.starting = false;

    if (!wasActive) {
      media.cleanupResources();
      render.showScreen('home');
      return;
    }

    if (reason === 'disconnected') {
      media.cleanupResources();
    } else {
      media.stopMediaOnly();
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'stop' }));
      }
    }

    render.buildSummary();
    render.showScreen('summary');
  }

  function init() {
    dom.navLinks.forEach((link) => {
      link.addEventListener('click', () => {
        const target = link.dataset.nav;
        if (target === 'meeting' && !state.active) return;
        if (target === 'summary' && state.transcriptLog.length === 0 && state.actionsLog.length === 0) return;
        render.showScreen(target);
      });
    });

    dom.startBtn.addEventListener('click', () => {
      startMeeting().catch((error) => {
        console.error('startMeeting failed:', error);
        media.cleanupResources();
        state.active = false;
        state.starting = false;
        dom.startBtn.disabled = false;
        render.showScreen('home');
        const message = error?.name === 'NotAllowedError'
          ? 'Microphone/camera access was denied. Please allow permissions and try again.'
          : error?.message || String(error);
        render.setStartError(message);
      });
    });

    dom.stopBtn.addEventListener('click', () => stopMeeting('user'));
    dom.newMeetingBtn.addEventListener('click', () => {
      closeWs();
      resetSessionId();
      render.showScreen('home');
      documents.loadDocumentWidget();
    });
  }

  window.MeetingAgent.session = {
    init,
    startMeeting,
    stopMeeting,
  };
})();
