window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core } = window.MeetingAgent;
  const { state, timeStr } = core;

  // ── Sponsor state ──
  const sponsorState = {
    kbConnected: false,
    meetingsArchived: 0,
    reportsGenerated: 0,
    reports: [],  // {report_id, query, summary, report_url}
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
  // Knowledge Base (DigitalOcean)
  // ═══════════════════════════════════════

  function updateKBStatus(data) {
    const connected = data && data.connected;
    sponsorState.kbConnected = connected;

    if (typeof data.meetings_archived === 'number') {
      sponsorState.meetingsArchived = data.meetings_archived;
    }

    if (dom.kbDot) {
      dom.kbDot.className = `inline-block w-2 h-2 rounded-full flex-shrink-0 ${connected ? 'bg-success' : 'bg-slate-500'}`;
    }
    if (dom.kbStatus) {
      dom.kbStatus.textContent = connected ? 'Connected' : 'Offline';
      dom.kbStatus.className = `text-[10px] font-bold uppercase tracking-wider ${connected ? 'text-success' : 'text-slate-500'}`;
    }
    updateKBCounter();
  }

  function updateKBCounter() {
    if (dom.kbCounter) {
      const parts = [`${sponsorState.meetingsArchived} meeting${sponsorState.meetingsArchived !== 1 ? 's' : ''} archived`];
      if (sponsorState.reportsGenerated > 0) {
        parts.push(`${sponsorState.reportsGenerated} report${sponsorState.reportsGenerated !== 1 ? 's' : ''}`);
      }
      dom.kbCounter.textContent = parts.join(' · ');
    }
  }

  function addReportToKB(payload) {
    if (!payload || !payload.report_id) return;
    sponsorState.reportsGenerated++;
    sponsorState.reports.push(payload);
    updateKBCounter();
    renderReports();
  }

  function renderReports() {
    const container = dom.kbReports;
    if (!container) return;
    container.innerHTML = '';
    for (const report of sponsorState.reports) {
      const wrapper = document.createElement('div');
      wrapper.className = 'flex flex-col gap-1 p-1.5 rounded bg-primary/5 border border-primary/20 card-enter';

      // Report query title
      const title = document.createElement('p');
      title.className = 'text-[10px] text-white font-medium truncate';
      title.textContent = report.query || 'Report';
      wrapper.appendChild(title);

      const meta = document.createElement('p');
      meta.className = 'text-[9px] text-slate-400 truncate';
      meta.textContent = `${report.row_count || 0} rows · ${(report.summary || '').slice(0, 60)}`;
      wrapper.appendChild(meta);

      // Links row
      const links = document.createElement('div');
      links.className = 'flex items-center gap-2 mt-0.5';

      // Chart.js report link
      const chartLink = document.createElement('a');
      chartLink.href = report.report_url;
      chartLink.target = '_blank';
      chartLink.className = 'flex items-center gap-1 text-[9px] text-primary hover:text-white transition-colors';
      chartLink.innerHTML = '<span class="material-symbols-outlined text-[11px]">bar_chart</span>Report';
      links.appendChild(chartLink);

      // Looker Studio link
      if (report.looker_url) {
        const lookerLink = document.createElement('a');
        lookerLink.href = report.looker_url;
        lookerLink.target = '_blank';
        lookerLink.className = 'flex items-center gap-1 text-[9px] text-cyan-400 hover:text-white transition-colors';
        lookerLink.innerHTML = '<span class="material-symbols-outlined text-[11px]">analytics</span>Looker Studio';
        links.appendChild(lookerLink);
      }

      wrapper.appendChild(links);
      container.appendChild(wrapper);
    }
  }

  function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  function flashMeetingArchived() {
    if (!dom.memoryFlash) return;
    dom.memoryFlash.classList.remove('hidden');
    dom.memoryFlash.classList.add('flex');
    setTimeout(() => {
      dom.memoryFlash.classList.add('hidden');
      dom.memoryFlash.classList.remove('flex');
    }, 3000);
  }

  // ═══════════════════════════════════════
  // DigitalOcean Knowledge Base Header Badge
  // ═══════════════════════════════════════

  function updateMemoryStatus(data) {
    const connected = data && data.connected;
    sponsorState.memoryConnected = connected;

    // Update header badge with Knowledge Base branding
    if (dom.memoryDot) {
      dom.memoryDot.className = `inline-block w-2 h-2 rounded-full flex-shrink-0 ${connected ? 'bg-success' : 'bg-slate-500'}`;
    }
    if (dom.memoryLabel) {
      dom.memoryLabel.textContent = connected ? 'Knowledge Base: Connected' : 'Knowledge Base: Offline';
      dom.memoryLabel.className = `text-[10px] font-bold uppercase tracking-wider ${connected ? 'text-success' : 'text-slate-500'}`;
    }

    // Also sync KB panel status
    updateKBStatus(data);

    // Handle meetings_archived increment flash
    if (data && typeof data.meetings_archived === 'number' && data.meetings_archived > sponsorState.meetingsArchived) {
      flashMeetingArchived();
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
      case 'memory_status':
        updateMemoryStatus(message.data || message);
        return true;
      case 'flow_status':
        updateFlowStatus(message.data || message);
        return true;
      case 'action': {
        // Intercept report actions to display in KB panel
        const data = message.data || message;
        if (data && data.type === 'report' && data.status === 'sent' && data.payload) {
          addReportToKB(data.payload);
        }
        return false; // still let render.js handle the action card
      }
      default:
        return false;
    }
  }

  // ═══════════════════════════════════════
  // Reset on new meeting
  // ═══════════════════════════════════════

  function resetSponsorState() {
    sponsorState.kbConnected = false;
    sponsorState.meetingsArchived = 0;
    sponsorState.reportsGenerated = 0;
    sponsorState.reports = [];
    sponsorState.memoryConnected = false;
    sponsorState.memoryCommitments = 0;
    sponsorState.memoryDismissed = false;
    sponsorState.flowAgents = {
      TranscriptAnalyzer: 'idle',
      SentimentMonitor: 'idle',
      ActionExecutor: 'idle',
      MeetingMemory: 'idle',
    };

    updateKBCounter();
    updateKBStatus({ connected: false });
    renderFlowAgents();
    if (dom.kbReports) dom.kbReports.innerHTML = '';

    if (dom.memoryCard) {
      dom.memoryCard.classList.add('hidden');
    }
    if (dom.memoryFlash) {
      dom.memoryFlash.classList.add('hidden');
      dom.memoryFlash.classList.remove('flex');
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
      // Knowledge Base panel
      kbPanel: document.getElementById('sponsor-kb-panel'),
      kbToggle: document.getElementById('sponsor-kb-toggle'),
      kbBody: document.getElementById('sponsor-kb-body'),
      kbChevron: document.getElementById('sponsor-kb-chevron'),
      kbDot: document.getElementById('sponsor-kb-dot'),
      kbStatus: document.getElementById('sponsor-kb-status'),
      kbCounter: document.getElementById('sponsor-kb-counter'),
      kbReports: document.getElementById('sponsor-kb-reports'),
      kbChatBtn: document.getElementById('sponsor-kb-chat-btn'),
      // Header memory badge
      memoryBadge: document.getElementById('sponsor-memory-badge'),
      memoryDot: document.getElementById('sponsor-memory-dot'),
      memoryLabel: document.getElementById('sponsor-memory-label'),
      memoryFlash: document.getElementById('sponsor-memory-flash'),
      memoryCard: document.getElementById('sponsor-memory-card'),
      memoryCardText: document.getElementById('sponsor-memory-card-text'),
      memoryDismiss: document.getElementById('sponsor-memory-dismiss'),
      // Railtracks flow
      flowToggle: document.getElementById('sponsor-flow-toggle'),
      flowBody: document.getElementById('sponsor-flow-body'),
      flowChevron: document.getElementById('sponsor-flow-chevron'),
    };

    // Knowledge Base collapse toggle
    if (dom.kbToggle) {
      dom.kbToggle.addEventListener('click', () => {
        togglePanel(dom.kbBody, dom.kbChevron);
      });
    }

    // Flow status collapse toggle
    if (dom.flowToggle) {
      dom.flowToggle.addEventListener('click', () => {
        togglePanel(dom.flowBody, dom.flowChevron);
      });
    }

    // Memory card dismiss
    if (dom.memoryDismiss) {
      dom.memoryDismiss.addEventListener('click', dismissMemoryCard);
    }

    updateKBCounter();
    renderFlowAgents();

    // Fetch KB status on init so it doesn't stay "Offline" by default
    fetch('/api/kb/status')
      .then((r) => r.json())
      .then((data) => {
        if (data) {
          updateKBStatus({ connected: data.available, meetings_archived: data.documents || 0 });
          updateMemoryStatus({ connected: data.available });
        }
      })
      .catch(() => { /* KB status fetch failed — stay offline */ });
  }

  window.MeetingAgent.sponsors = {
    init,
    handleSponsorMessage,
    resetSponsorState,
    updateKBStatus,
    updateMemoryStatus,
    updateFlowStatus,
  };
})();
