window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core } = window.MeetingAgent;
  const { state, timeStr } = core;

  // ── Sponsor state ──
  const sponsorState = {
    auditTrail: [],
    auditCount: 0,
    killSwitchActive: false,
    memoryConnected: false,
    memoryCommitments: 0,
    memoryDismissed: false,
    flowAgents: {
      TranscriptAnalyzer: 'idle',
      SentimentMonitor: 'idle',
      ActionExecutor: 'idle',
      MeetingMemory: 'idle',
    },
  };

  // ── DOM references (grabbed once on init) ──
  let dom = {};

  // ── Action type icons ──
  const ACTION_ICONS = {
    slack: '\u{1F4AC}',
    calendar: '\u{1F4C5}',
    task: '\u2705',
    document: '\u{1F4C4}',
  };

  // ── Sentiment badge config ──
  const SENTIMENT_BADGES = {
    positive: { text: 'Positive', cls: 'bg-success/20 text-success border-success/30' },
    happiness: { text: 'Positive', cls: 'bg-success/20 text-success border-success/30' },
    neutral: { text: 'Neutral', cls: 'bg-slate-500/20 text-slate-400 border-slate-500/30' },
    negative: { text: 'Negative', cls: 'bg-danger/20 text-danger border-danger/30' },
    uncertain: { text: 'Uncertain', cls: 'bg-warning/20 text-warning border-warning/30' },
  };

  // ── Flow agent dot colors ──
  const FLOW_DOT_COLORS = {
    running: 'bg-success',
    idle: 'bg-slate-500',
    blocked: 'bg-danger',
  };

  // ═══════════════════════════════════════
  // Unkey Audit Trail
  // ═══════════════════════════════════════

  function addAuditEntry(entry) {
    if (sponsorState.killSwitchActive) return;

    const type = (entry.action_type || entry.type || 'task').toLowerCase();
    const icon = ACTION_ICONS[type] || '\u2705';
    const payload = entry.payload_summary || entry.summary || '';
    const payloadShort = payload.length > 80 ? payload.slice(0, 80) + '...' : payload;
    const sentiment = (entry.sentiment || 'neutral').toLowerCase();
    const ts = entry.timestamp || timeStr();
    const keyId = entry.key_id || 'uk_' + Math.random().toString(36).slice(2, 10);

    const record = { icon, type, payloadShort, sentiment, ts, keyId };
    sponsorState.auditTrail.unshift(record);
    sponsorState.auditCount += 1;

    renderAuditEntry(record);
    updateAuditCounter();
  }

  function renderAuditEntry(record) {
    if (!dom.auditList) return;

    const badge = SENTIMENT_BADGES[record.sentiment] || SENTIMENT_BADGES.neutral;

    const row = document.createElement('div');
    row.className = 'flex items-start gap-2.5 p-2.5 rounded-lg bg-bg-dark border border-border-muted hover:border-primary/20 transition-colors action-card-enter';

    const iconEl = document.createElement('span');
    iconEl.className = 'text-base flex-shrink-0 mt-0.5';
    iconEl.textContent = record.icon;

    const body = document.createElement('div');
    body.className = 'flex-1 min-w-0';

    const topRow = document.createElement('div');
    topRow.className = 'flex items-center gap-2 mb-1';

    const sentimentEl = document.createElement('span');
    sentimentEl.className = `text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border ${badge.cls}`;
    sentimentEl.textContent = badge.text;

    const tsEl = document.createElement('span');
    tsEl.className = 'text-[10px] text-slate-500 ml-auto flex-shrink-0';
    tsEl.textContent = record.ts;

    topRow.append(sentimentEl, tsEl);

    const payloadEl = document.createElement('p');
    payloadEl.className = 'text-[11px] text-slate-300 leading-snug truncate';
    payloadEl.textContent = record.payloadShort;

    const keyEl = document.createElement('p');
    keyEl.className = 'text-[9px] text-slate-600 font-mono mt-1';
    keyEl.textContent = record.keyId;

    body.append(topRow, payloadEl, keyEl);
    row.append(iconEl, body);
    dom.auditList.prepend(row);
  }

  function updateAuditCounter() {
    if (dom.auditCounter) {
      dom.auditCounter.textContent = `${sponsorState.auditCount} action${sponsorState.auditCount !== 1 ? 's' : ''} audited this session`;
    }
  }

  async function killSwitch() {
    if (sponsorState.killSwitchActive) return;

    try {
      const sessionId = state.currentSessionId || 'unknown';
      await fetch('/api/unkey/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (err) {
      console.warn('Kill switch request failed:', err);
    }

    sponsorState.killSwitchActive = true;

    if (dom.killBtn) {
      dom.killBtn.disabled = true;
      dom.killBtn.textContent = 'AGENT KILLED';
      dom.killBtn.className = dom.killBtn.className
        .replace('bg-danger', 'bg-slate-700')
        .replace('hover:bg-danger/90', '')
        .replace('border-danger/50', 'border-slate-600');
    }

    if (dom.auditPanel) {
      dom.auditPanel.style.opacity = '0.5';
      dom.auditPanel.style.pointerEvents = 'none';
    }
  }

  // ═══════════════════════════════════════
  // DigitalOcean Memory Indicator
  // ═══════════════════════════════════════

  function updateMemoryStatus(data) {
    const connected = data && data.connected;
    sponsorState.memoryConnected = connected;

    if (dom.memoryDot) {
      dom.memoryDot.className = `inline-block w-2 h-2 rounded-full flex-shrink-0 ${connected ? 'bg-success' : 'bg-slate-500'}`;
    }
    if (dom.memoryLabel) {
      dom.memoryLabel.textContent = connected ? 'Meeting Memory: Connected' : 'Meeting Memory: Offline';
      dom.memoryLabel.className = `text-[10px] font-bold uppercase tracking-wider ${connected ? 'text-success' : 'text-slate-500'}`;
    }

    if (connected && data.open_commitments && data.open_commitments > 0 && !sponsorState.memoryDismissed) {
      sponsorState.memoryCommitments = data.open_commitments;
      showMemoryCard(data.open_commitments);
    }
  }

  function showMemoryCard(count) {
    if (!dom.memoryCard) return;
    dom.memoryCard.classList.remove('hidden');
    if (dom.memoryCardText) {
      dom.memoryCardText.textContent = `Prior context loaded: ${count} open commitment${count !== 1 ? 's' : ''} from past meetings`;
    }
  }

  function dismissMemoryCard() {
    sponsorState.memoryDismissed = true;
    if (dom.memoryCard) {
      dom.memoryCard.classList.add('hidden');
    }
  }

  // ═══════════════════════════════════════
  // Railtracks Flow Status
  // ═══════════════════════════════════════

  function updateFlowStatus(data) {
    if (!data || !data.agents) return;

    for (const [name, status] of Object.entries(data.agents)) {
      if (name in sponsorState.flowAgents) {
        sponsorState.flowAgents[name] = status || 'idle';
      }
    }

    renderFlowAgents();
  }

  function renderFlowAgents() {
    const agentNames = Object.keys(sponsorState.flowAgents);
    for (const name of agentNames) {
      const status = sponsorState.flowAgents[name];
      const dotEl = document.getElementById(`flow-dot-${name}`);
      const labelEl = document.getElementById(`flow-label-${name}`);
      if (dotEl) {
        const colorCls = FLOW_DOT_COLORS[status] || FLOW_DOT_COLORS.idle;
        const isPulsing = status === 'running';
        dotEl.className = `inline-block w-2 h-2 rounded-full flex-shrink-0 ${colorCls}${isPulsing ? ' pulse-dot' : ''}`;
      }
      if (labelEl) {
        labelEl.className = `text-[10px] ${status === 'running' ? 'text-slate-300' : status === 'blocked' ? 'text-danger/70' : 'text-slate-500'}`;
      }
    }
  }

  // ═══════════════════════════════════════
  // WebSocket message handler
  // ═══════════════════════════════════════

  function handleSponsorMessage(message) {
    if (!message || !message.type) return false;

    switch (message.type) {
      case 'audit_trail':
        addAuditEntry(message.data || message);
        return true;
      case 'memory_status':
        updateMemoryStatus(message.data || message);
        return true;
      case 'flow_status':
        updateFlowStatus(message.data || message);
        return true;
      default:
        return false;
    }
  }

  // ═══════════════════════════════════════
  // Reset on new meeting
  // ═══════════════════════════════════════

  function resetSponsorState() {
    sponsorState.auditTrail = [];
    sponsorState.auditCount = 0;
    sponsorState.killSwitchActive = false;
    sponsorState.memoryConnected = false;
    sponsorState.memoryCommitments = 0;
    sponsorState.memoryDismissed = false;
    sponsorState.flowAgents = {
      TranscriptAnalyzer: 'idle',
      SentimentMonitor: 'idle',
      ActionExecutor: 'idle',
      MeetingMemory: 'idle',
    };

    if (dom.auditList) dom.auditList.textContent = '';
    updateAuditCounter();
    renderFlowAgents();

    if (dom.killBtn) {
      dom.killBtn.disabled = false;
      dom.killBtn.textContent = 'KILL SWITCH';
      dom.killBtn.className = 'w-full h-9 bg-danger hover:bg-danger/90 text-white text-xs font-bold uppercase tracking-wider rounded-lg border border-danger/50 transition-colors flex items-center justify-center gap-1.5';
    }
    if (dom.auditPanel) {
      dom.auditPanel.style.opacity = '';
      dom.auditPanel.style.pointerEvents = '';
    }
    if (dom.memoryCard) {
      dom.memoryCard.classList.add('hidden');
    }
    updateMemoryStatus({ connected: false });
  }

  // ═══════════════════════════════════════
  // Toggle panels
  // ═══════════════════════════════════════

  function togglePanel(bodyEl, chevronEl) {
    if (!bodyEl || !chevronEl) return;
    const expanded = !bodyEl.classList.contains('hidden');
    if (expanded) {
      bodyEl.classList.add('hidden');
      chevronEl.textContent = 'expand_more';
    } else {
      bodyEl.classList.remove('hidden');
      chevronEl.textContent = 'expand_less';
    }
  }

  // ═══════════════════════════════════════
  // Init
  // ═══════════════════════════════════════

  function init() {
    dom = {
      auditPanel: document.getElementById('sponsor-audit-panel'),
      auditList: document.getElementById('sponsor-audit-list'),
      auditCounter: document.getElementById('sponsor-audit-counter'),
      killBtn: document.getElementById('sponsor-kill-btn'),
      auditToggle: document.getElementById('sponsor-audit-toggle'),
      auditBody: document.getElementById('sponsor-audit-body'),
      auditChevron: document.getElementById('sponsor-audit-chevron'),
      memoryBadge: document.getElementById('sponsor-memory-badge'),
      memoryDot: document.getElementById('sponsor-memory-dot'),
      memoryLabel: document.getElementById('sponsor-memory-label'),
      memoryCard: document.getElementById('sponsor-memory-card'),
      memoryCardText: document.getElementById('sponsor-memory-card-text'),
      memoryDismiss: document.getElementById('sponsor-memory-dismiss'),
      flowToggle: document.getElementById('sponsor-flow-toggle'),
      flowBody: document.getElementById('sponsor-flow-body'),
      flowChevron: document.getElementById('sponsor-flow-chevron'),
    };

    // Audit trail collapse toggle
    if (dom.auditToggle) {
      dom.auditToggle.addEventListener('click', () => {
        togglePanel(dom.auditBody, dom.auditChevron);
      });
    }

    // Flow status collapse toggle
    if (dom.flowToggle) {
      dom.flowToggle.addEventListener('click', () => {
        togglePanel(dom.flowBody, dom.flowChevron);
      });
    }

    // Kill switch
    if (dom.killBtn) {
      dom.killBtn.addEventListener('click', killSwitch);
    }

    // Memory card dismiss
    if (dom.memoryDismiss) {
      dom.memoryDismiss.addEventListener('click', dismissMemoryCard);
    }

    updateAuditCounter();
    renderFlowAgents();
  }

  window.MeetingAgent.sponsors = {
    init,
    handleSponsorMessage,
    resetSponsorState,
    addAuditEntry,
    updateMemoryStatus,
    updateFlowStatus,
  };
})();
