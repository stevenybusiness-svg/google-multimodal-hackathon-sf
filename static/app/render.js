window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core } = window.MeetingAgent;
  const { dom, state, sentimentConfig, overlayColors, actionBadge, timeStr } = core;

  function showScreen(name) {
    state.currentScreen = name;
    for (const [key, element] of Object.entries(dom.screens)) {
      element.classList.toggle('active', key === name);
    }
    dom.navLinks.forEach((link) => {
      const target = link.dataset.nav;
      const isActive = target === name;
      link.classList.toggle('text-primary', isActive);
      link.classList.toggle('text-slate-400', !isActive);
      const label = link.querySelector('p');
      if (label) {
        label.classList.toggle('font-bold', isActive);
        label.classList.toggle('font-medium', !isActive);
      }
    });
  }

  function setStartError(message) {
    if (!message) {
      dom.startError.textContent = '';
      dom.startError.classList.add('hidden');
      return;
    }
    dom.startError.textContent = message;
    dom.startError.classList.remove('hidden');
  }

  function resetMeetingState() {
    dom.transcript.textContent = '';
    dom.actionsFeed.textContent = '';
    state.transcriptLog = [];
    state.actionsLog = [];
    state.actionNewCount = 0;
    state.currentLineEl = null;
    state.currentLineText = '';
    state.lastFragTime = 0;
    state.lastVisionResult = null;
    dom.actionCount.classList.add('hidden');
    dom.sentimentPill.classList.add('hidden');
    dom.processingInd.classList.add('hidden');
    dom.processingInd.classList.remove('flex');
    state.meetingStartTime = new Date();
    // Reset sentiment borders to neutral
    applySentimentBorders('neutral');
  }

  // Map raw sentiment values to one of our four visual categories
  function sentimentCategory(sentiment) {
    if (sentiment === 'positive' || sentiment === 'happiness') return 'positive';
    if (sentiment === 'negative' || sentiment === 'anger' || sentiment === 'sadness') return 'negative';
    if (sentiment === 'uncertain' || sentiment === 'surprise') return 'uncertain';
    return 'neutral';
  }

  function applySentimentBorders(sentiment) {
    const category = sentimentCategory(sentiment);
    const classes = ['sentiment-positive', 'sentiment-negative', 'sentiment-uncertain', 'sentiment-neutral'];

    // Pipeline panel
    const pipelinePanel = document.getElementById('meeting-pipeline-panel');
    if (pipelinePanel) {
      for (const cls of classes) pipelinePanel.classList.remove(cls);
      pipelinePanel.classList.add('sentiment-' + category);
    }

    // Webcam video element (fixed position, bottom-right)
    if (dom.visionVideo && dom.visionVideo.style.display !== 'none' && !dom.visionVideo.classList.contains('hidden')) {
      const colorMap = { positive: '#3fb950', negative: '#f85149', uncertain: '#e3b341', neutral: '#30363d' };
      const shadowMap = {
        positive: '0 0 15px rgba(63,185,80,0.4), 0 4px 16px rgba(0,0,0,0.6)',
        negative: '0 0 15px rgba(248,81,73,0.4), 0 4px 16px rgba(0,0,0,0.6)',
        uncertain: '0 0 15px rgba(227,179,65,0.4), 0 4px 16px rgba(0,0,0,0.6)',
        neutral: '0 4px 16px rgba(0,0,0,0.6)',
      };
      dom.visionVideo.style.borderColor = colorMap[category];
      dom.visionVideo.style.boxShadow = shadowMap[category];
      dom.visionVideo.style.transition = 'border-color 0.5s ease, box-shadow 0.5s ease';
    }
  }

  function updateSentiment(value) {
    const sentiment = (value || 'neutral').toLowerCase();
    const config = sentimentConfig[sentiment] || sentimentConfig.neutral;
    dom.sentimentPill.classList.remove('hidden');
    dom.sentimentPill.className = [
      'flex', 'items-center', 'gap-1.5', 'px-2', 'py-0.5', 'rounded',
      'border', config.borderClass, config.bgClass, 'text-[10px]', config.textClass,
      'font-mono', 'uppercase', 'tracking-wider',
    ].join(' ');
    dom.sentimentPill.querySelector('.material-symbols-outlined').textContent = config.icon;
    dom.sentimentText.textContent = sentiment.toUpperCase();
    applySentimentBorders(sentiment);
  }

  function drawSentimentOverlay(result, sourceW, sourceH) {
    const ctx = dom.visionCanvas.getContext('2d');
    const canvasWidth = dom.visionCanvas.width;
    const canvasHeight = dom.visionCanvas.height;
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    if (!result || !result.face_box) return;

    const { face_box: faceBox, sentiment } = result;
    const color = overlayColors[sentiment] || overlayColors.neutral;
    // Use cover scaling to match object-fit:cover on the video element
    const scale = Math.max(canvasWidth / sourceW, canvasHeight / sourceH);
    const scaledW = sourceW * scale;
    const scaledH = sourceH * scale;
    const offsetX = (canvasWidth - scaledW) / 2;
    const offsetY = (canvasHeight - scaledH) / 2;
    const x = faceBox.x * scale + offsetX;
    const y = faceBox.y * scale + offsetY;
    const w = (faceBox.w || faceBox.width) * scale;
    const h = (faceBox.h || faceBox.height) * scale;

    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    const radius = 6;
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.arcTo(x + w, y, x + w, y + radius, radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.arcTo(x + w, y + h, x + w - radius, y + h, radius);
    ctx.lineTo(x + radius, y + h);
    ctx.arcTo(x, y + h, x, y + h - radius, radius);
    ctx.lineTo(x, y + radius);
    ctx.arcTo(x, y, x + radius, y, radius);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();

    const label = (sentiment || 'neutral').toUpperCase();
    ctx.font = 'bold 9px monospace';
    const metrics = ctx.measureText(label);
    const labelWidth = metrics.width + 8;
    const labelHeight = 14;
    const labelX = x + (w - labelWidth) / 2;
    const labelY = Math.max(0, y - labelHeight - 3);
    ctx.fillStyle = 'rgba(0,0,0,0.75)';
    ctx.beginPath();
    ctx.roundRect(labelX, labelY, labelWidth, labelHeight, 3);
    ctx.fill();
    ctx.fillStyle = color;
    ctx.fillText(label, labelX + 4, labelY + 10);

    // Red warning arrows for negative/uncertain sentiment
    const isNeg = sentiment === 'anger' || sentiment === 'sadness' || sentiment === 'negative' || sentiment === 'uncertain';
    if (isNeg) {
      ctx.save();
      ctx.fillStyle = '#ef4444';
      ctx.shadowColor = '#ef4444';
      ctx.shadowBlur = 6;
      const arrowSize = 8;
      const arrowPositions = [
        { ax: x - 14, ay: y + h * 0.3 },
        { ax: x - 14, ay: y + h * 0.6 },
        { ax: x + w + 6, ay: y + h * 0.3 },
        { ax: x + w + 6, ay: y + h * 0.6 },
      ];
      for (const pos of arrowPositions) {
        ctx.beginPath();
        ctx.moveTo(pos.ax, pos.ay);
        ctx.lineTo(pos.ax + arrowSize, pos.ay);
        ctx.lineTo(pos.ax + arrowSize / 2, pos.ay + arrowSize);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();
    }
  }

  function createActionCard(action, container) {
    const type = (action.type || 'unknown').toLowerCase();
    const badge = actionBadge[type] || { label: type, colorClasses: 'bg-slate-500/15 text-slate-400 border-slate-500/30' };
    const timestamp = timeStr();

    let payloadText;
    if (type === 'document' && action.payload) {
      const payload = action.payload;
      payloadText = `📝 ${payload.title || payload.filename || 'Document'} — ${payload.changes || 'Updated'}`;
    } else if (type === 'infra' && action.payload) {
      const p = action.payload;
      payloadText = `VM: ${p.name || 'unnamed'} (${p.machine_type || 'e2-medium'}, ${p.zone || 'us-central1-a'}) — ${p.status || 'pending'}`;
    } else if (type === 'report' && action.payload) {
      const p = action.payload;
      payloadText = `📊 ${p.query || 'Report'} — ${p.row_count || 0} rows`;
      if (p.report_url) {
        payloadText += ` · <a href="${p.report_url}" target="_blank" class="text-primary underline">View Report</a>`;
      }
    } else {
      payloadText = action.payload
        ? (typeof action.payload === 'object'
            ? (action.payload.text || action.payload.summary || action.payload.what || JSON.stringify(action.payload))
            : String(action.payload))
        : JSON.stringify(action);
    }

    // Sentiment-aware styling: use per-action sentiment from backend; fall back to global
    const sentiment = (action.sentiment || action.payload?.sentiment || state.currentSentiment || 'neutral').toLowerCase();
    const sentimentMeta = {
      positive:  { border: 'border-l-success',   icon: 'verified',          label: 'Confident',             cls: 'text-success' },
      happiness: { border: 'border-l-success',   icon: 'verified',          label: 'Confident',             cls: 'text-success' },
      neutral:   { border: 'border-l-slate-500', icon: 'check_circle',      label: 'Acknowledged',          cls: 'text-slate-400' },
      negative:  { border: 'border-l-danger',    icon: 'flag',              label: 'Review — negative tone', cls: 'text-danger' },
      uncertain: { border: 'border-l-warning',   icon: 'help',              label: 'Review — uncertain',     cls: 'text-warning' },
    };
    const sm = sentimentMeta[sentiment] || sentimentMeta.neutral;

    const isBlocked = action.status === 'blocked';
    const isProceeded = !isBlocked && (action.status === 'sent' || action.status === 'logged');

    // Override sentiment display for blocked actions
    const displaySm = isBlocked
      ? { border: 'border-l-danger', icon: 'block', label: 'Blocked — negative sentiment', cls: 'text-danger' }
      : sm;

    const card = document.createElement('div');
    let glowClass = '';
    if (isBlocked) {
      glowClass = ' ring-2 ring-danger/40';
    } else if (isProceeded) {
      glowClass = ' ring-1 ring-success/30';
    }
    card.className = `action-card-enter p-3 rounded-lg bg-bg-dark border border-border-muted hover:border-primary/30 transition-colors border-l-2 ${displaySm.border}${glowClass}`;

    const header = document.createElement('div');
    header.className = 'flex items-center justify-between mb-2';
    const leftHeader = document.createElement('div');
    leftHeader.className = 'flex items-center gap-2';
    const badgeEl = document.createElement('span');
    badgeEl.className = `text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded border ${badge.colorClasses}`;
    badgeEl.textContent = badge.label;
    const sentimentTag = document.createElement('span');
    sentimentTag.className = `text-[10px] ${displaySm.cls} flex items-center gap-0.5`;
    sentimentTag.innerHTML = `<span class="material-symbols-outlined text-[11px]">${displaySm.icon}</span>${displaySm.label}`;
    leftHeader.append(badgeEl, sentimentTag);
    const timeEl = document.createElement('span');
    timeEl.className = 'text-[10px] text-slate-500';
    timeEl.textContent = timestamp;
    header.append(leftHeader, timeEl);

    const summary = document.createElement('p');
    summary.className = 'text-xs text-slate-300 leading-snug';
    if (type === 'report') {
      summary.innerHTML = payloadText;
    } else {
      summary.textContent = payloadText;
    }
    card.append(header, summary);

    const statusEl = document.createElement('p');
    statusEl.className = 'text-[10px] mt-1 font-mono uppercase tracking-wide';
    if (isBlocked) {
      statusEl.className += ' text-danger';
      statusEl.textContent = 'BLOCKED';
      card.appendChild(statusEl);
    } else if (action.status === 'failed' || action.error) {
      statusEl.className += ' text-danger';
      statusEl.textContent = `failed${action.error ? `: ${action.error}` : ''}`;
      card.appendChild(statusEl);
    } else if (action.status === 'skipped') {
      statusEl.className += ' text-warning';
      statusEl.textContent = 'skipped';
      card.appendChild(statusEl);
    } else if (action.status && action.status !== 'sent') {
      statusEl.className += ' text-slate-400';
      statusEl.textContent = action.status;
      card.appendChild(statusEl);
    }

    container.prepend(card);
    return { type, payload: payloadText, ts: timestamp, status: action.status || 'sent', error: action.error || null, sentiment };
  }

  function buildSummary() {
    if (state.transcriptLog.length > 0) {
      const first = state.transcriptLog[0].ts;
      const last = state.transcriptLog[state.transcriptLog.length - 1].ts;
      dom.summaryTimeRange.textContent = `${first} - ${last}`;
    } else {
      dom.summaryTimeRange.textContent = '';
    }

    dom.summaryTranscript.textContent = '';
    state.transcriptLog.forEach((entry) => {
      const group = document.createElement('div');
      const tsEl = document.createElement('p');
      tsEl.className = 'text-primary text-[10px] mb-1';
      tsEl.textContent = `[${entry.ts}]`;
      const textEl = document.createElement('p');
      textEl.className = 'text-text-main';
      textEl.textContent = entry.text;
      group.append(tsEl, textEl);
      dom.summaryTranscript.appendChild(group);
    });
    if (state.transcriptLog.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'text-slate-500 text-sm';
      empty.textContent = 'No transcript recorded.';
      dom.summaryTranscript.appendChild(empty);
    }

    dom.summaryActions.textContent = '';
    dom.summaryActionCount.textContent = `${state.actionsLog.length} Action${state.actionsLog.length !== 1 ? 's' : ''} Captured`;
    state.actionsLog.forEach((entry) => {
      const badge = actionBadge[entry.type] || { label: entry.type, colorClasses: 'bg-slate-500/15 text-slate-400 border-slate-500/30' };
      const sMeta = {
        positive:  { border: 'border-l-success',   icon: 'verified',     label: 'Confident',              cls: 'text-success' },
        happiness: { border: 'border-l-success',   icon: 'verified',     label: 'Confident',              cls: 'text-success' },
        neutral:   { border: 'border-l-slate-500', icon: 'check_circle', label: 'Acknowledged',           cls: 'text-slate-400' },
        negative:  { border: 'border-l-danger',    icon: 'flag',         label: 'Review — negative tone', cls: 'text-danger' },
        uncertain: { border: 'border-l-warning',   icon: 'help',         label: 'Review — uncertain',     cls: 'text-warning' },
      };
      const esm = sMeta[entry.sentiment] || sMeta.neutral;
      const card = document.createElement('div');
      let summaryGlow = '';
      if (entry.status === 'blocked') {
        summaryGlow = ' ring-2 ring-danger/40';
      } else if (entry.status === 'sent' || entry.status === 'logged') {
        summaryGlow = ' ring-1 ring-success/30';
      }
      card.className = `p-4 rounded-lg bg-bg-dark border border-border-muted hover:border-primary/30 transition-colors border-l-2 ${esm.border}${summaryGlow}`;
      const header = document.createElement('div');
      header.className = 'flex items-start justify-between mb-2';
      const left = document.createElement('div');
      left.className = 'flex items-center gap-2';
      const iconBox = document.createElement('div');
      iconBox.className = 'size-8 rounded bg-slate-800 flex items-center justify-center';
      const icon = document.createElement('span');
      icon.className = 'material-symbols-outlined text-sm text-slate-400';
      icon.textContent = entry.type === 'slack' ? 'tag' : entry.type === 'calendar' ? 'event' : entry.type === 'document' ? 'description' : entry.type === 'email' ? 'mail' : entry.type === 'infra' ? 'cloud' : 'task_alt';
      iconBox.appendChild(icon);
      const label = document.createElement('p');
      label.className = 'text-xs font-bold';
      label.textContent = badge.label;
      left.append(iconBox, label);
      const status = document.createElement('span');
      status.className = `text-[10px] px-1.5 py-0.5 rounded uppercase font-bold ${
        entry.status === 'failed'
          ? 'bg-danger/10 text-danger'
          : entry.status === 'skipped'
            ? 'bg-warning/10 text-warning'
            : entry.status === 'blocked'
              ? 'bg-danger/10 text-danger'
              : 'bg-success/10 text-success'
      }`;
      status.textContent = entry.status === 'blocked' ? 'BLOCKED' : (entry.status || 'sent');
      header.append(left, status);

      const body = document.createElement('p');
      body.className = 'text-xs text-slate-300 leading-snug';
      body.textContent = entry.payload;

      const footer = document.createElement('div');
      footer.className = 'mt-3 pt-3 border-t border-border-muted flex justify-between items-center';
      const footerTime = document.createElement('span');
      footerTime.className = 'text-[10px] text-slate-500';
      footerTime.textContent = entry.ts;
      const sentimentFooter = document.createElement('span');
      sentimentFooter.className = `text-[10px] ${esm.cls} flex items-center gap-0.5`;
      sentimentFooter.innerHTML = `<span class="material-symbols-outlined text-[11px]">${esm.icon}</span>${esm.label}`;
      footer.append(footerTime, sentimentFooter);
      card.append(header, body, footer);

      if (entry.error) {
        const errorEl = document.createElement('p');
        errorEl.className = 'text-[10px] text-danger mt-2 font-mono';
        errorEl.textContent = entry.error;
        card.appendChild(errorEl);
      }

      dom.summaryActions.appendChild(card);
    });
    if (state.actionsLog.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'text-slate-500 text-sm p-2';
      empty.textContent = 'No actions were detected during this meeting.';
      dom.summaryActions.appendChild(empty);
    }
  }

  // --- "Analyzing" pulse in actions panel for real-time feel ---
  let _analyzingEl = null;
  let _analyzingTimeout = null;

  function _showAnalyzing() {
    if (_analyzingEl) return; // already showing
    _analyzingEl = document.createElement('div');
    _analyzingEl.className = 'p-3 rounded-lg bg-primary/5 border border-primary/20 flex items-center gap-3 action-card-enter';
    _analyzingEl.innerHTML = `
      <span class="pulse-dot inline-block w-2 h-2 rounded-full bg-primary flex-shrink-0"></span>
      <span class="text-xs text-primary/80 font-medium">Analyzing transcript...</span>
    `;
    dom.actionsFeed.prepend(_analyzingEl);
  }

  function _hideAnalyzing() {
    if (_analyzingEl) {
      _analyzingEl.remove();
      _analyzingEl = null;
    }
    if (_analyzingTimeout) {
      clearTimeout(_analyzingTimeout);
      _analyzingTimeout = null;
    }
  }

  // --- Interim (partial) transcript: near-real-time text as user speaks ---
  let _interimEl = null;

  function handleInterimMessage(data) {
    const text = (data && data.text) || '';
    if (!text) return;

    if (!_interimEl) {
      const line = document.createElement('div');
      const tsSpan = document.createElement('span');
      tsSpan.className = 'text-slate-500 text-[10px]';
      tsSpan.textContent = `[${timeStr()}] `;
      const textSpan = document.createElement('span');
      textSpan.className = 'text-slate-400 italic';
      textSpan.textContent = text;
      line.append(tsSpan, textSpan);
      dom.transcript.appendChild(line);
      _interimEl = line;
    } else {
      const textSpan = _interimEl.querySelector('span:last-child');
      if (textSpan) textSpan.textContent = text;
    }
    dom.transcript.scrollTop = dom.transcript.scrollHeight;
    dom.processingInd.classList.remove('hidden');
    dom.processingInd.classList.add('flex');
    _showAnalyzing();
  }

  function _clearInterim() {
    if (_interimEl) {
      _interimEl.remove();
      _interimEl = null;
    }
  }

  // --- Final transcript: committed, accurate text ---
  function handleTranscriptMessage(data) {
    const text = (data && data.text) || '';
    if (!text) return;

    _clearInterim();
    const timestamp = timeStr();

    // Cloud STT finals are complete utterances — always a new line
    const line = document.createElement('div');
    const tsSpan = document.createElement('span');
    tsSpan.className = 'text-primary text-[10px]';
    tsSpan.textContent = `[${timestamp}] `;
    const textSpan = document.createElement('span');
    textSpan.className = 'text-text-main';
    textSpan.textContent = text;
    line.append(tsSpan, textSpan);
    dom.transcript.appendChild(line);
    state.transcriptLog.push({ ts: timestamp, text });

    dom.transcript.scrollTop = dom.transcript.scrollHeight;
    dom.processingInd.classList.remove('hidden');
    dom.processingInd.classList.add('flex');

    // Show analyzing indicator immediately for real-time feel
    _showAnalyzing();
    // Auto-hide after 12s if no action arrives (e.g. filler speech)
    if (_analyzingTimeout) clearTimeout(_analyzingTimeout);
    _analyzingTimeout = setTimeout(_hideAnalyzing, 12000);
  }

  function handleActionMessage(action) {
    if (!action) return;
    _hideAnalyzing();
    const entry = createActionCard(action, dom.actionsFeed);
    state.actionsLog.push(entry);
    state.actionNewCount += 1;
    if (state.currentScreen === 'meeting') {
      dom.actionCount.classList.remove('hidden');
      dom.actionCount.textContent = `${state.actionNewCount} NEW`;
    }
    if (window.MeetingAgent.documents) {
      window.MeetingAgent.documents.applyAction(action);
    }
    if (state.currentScreen === 'summary') {
      buildSummary();
    }
    dom.processingInd.classList.add('hidden');
    dom.processingInd.classList.remove('flex');
  }

  function handleSentimentMessage(data) {
    const value = (data && data.value) || 'neutral';
    state.currentSentiment = value;
    updateSentiment(value);
    // Trigger canvas redraw with new sentiment color if we have a stored face position
    if (state.lastVisionResult && state.lastVisionResult.face_box && !state.faceDetector) {
      const vid = dom.visionVideo;
      if (vid && vid.videoWidth && vid.videoHeight) {
        // Map transcript sentiment to overlay-compatible value
        const mapped = value === 'positive' ? 'happiness' : value === 'negative' ? 'anger' : value;
        const tempResult = { ...state.lastVisionResult, sentiment: mapped };
        drawSentimentOverlay(tempResult, vid.videoWidth, vid.videoHeight);
      }
    }
    _hideAnalyzing();
    dom.processingInd.classList.add('hidden');
    dom.processingInd.classList.remove('flex');
  }

  function handleStatusMessage(data) {
    const text = (data && data.text) || String(data);
    dom.statusText.textContent = text;
  }

  window.MeetingAgent.render = {
    showScreen,
    setStartError,
    resetMeetingState,
    updateSentiment,
    drawSentimentOverlay,
    buildSummary,
    createActionCard,
    handleTranscriptMessage,
    handleInterimMessage,
    handleActionMessage,
    handleSentimentMessage,
    handleStatusMessage,
  };
})();
