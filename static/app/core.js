window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const dom = {
    screens: {
      home: document.getElementById('screen-home'),
      pipeline: document.getElementById('screen-pipeline'),
      meeting: document.getElementById('screen-meeting'),
      summary: document.getElementById('screen-summary'),
    },
    startBtn: document.getElementById('start-btn'),
    stopBtn: document.getElementById('stop-btn'),
    newMeetingBtn: document.getElementById('new-meeting-btn'),
    startError: document.getElementById('start-error'),
    micLevel: document.getElementById('mic-level'),
    transcript: document.getElementById('transcript'),
    actionsFeed: document.getElementById('actions-feed'),
    statusChip: document.getElementById('status-chip'),
    statusText: document.getElementById('status-text'),
    sentimentPill: document.getElementById('sentiment-pill'),
    sentimentText: document.getElementById('sentiment-text'),
    actionCount: document.getElementById('action-count'),
    processingInd: document.getElementById('processing-indicator'),
    bottomNav: document.getElementById('bottom-nav'),
    navLinks: document.getElementById('bottom-nav').querySelectorAll('[data-nav]'),
    summaryTranscript: document.getElementById('summary-transcript'),
    summaryActions: document.getElementById('summary-actions'),
    summaryTimeRange: document.getElementById('summary-time-range'),
    summaryActionCount: document.getElementById('summary-action-count'),
    pipelineCanvas: document.getElementById('pipeline-canvas'),
    pipelineActions: document.getElementById('pipeline-actions'),
    pipelineStatusText: document.getElementById('pipeline-status-text'),
    pipelineSentimentPill: document.getElementById('pipeline-sentiment-pill'),
    pipelineSentimentText: document.getElementById('pipeline-sentiment-text'),
    pipelineMicLevel: document.getElementById('pipeline-mic-level'),
    pipelineStopBtn: document.getElementById('pipeline-stop-btn'),
    pipelineEmptyState: document.getElementById('pipeline-empty-state'),
    visionVideo: document.getElementById('vision-video'),
    visionCanvas: document.getElementById('vision-canvas'),
    docWidgetContent: document.getElementById('doc-widget-content'),
    docExpandBtn: document.getElementById('doc-expand-btn'),
    docDownloadBtn: document.getElementById('doc-download-btn'),
    docModal: document.getElementById('doc-modal'),
    docModalTitle: document.getElementById('doc-modal-title'),
    docModalBody: document.getElementById('doc-modal-body'),
    docModalClose: document.getElementById('doc-modal-close'),
  };

  const state = {
    ws: null,
    audioCtx: null,
    processor: null,
    micStream: null,
    videoStream: null,
    frameInterval: null,
    active: false,
    starting: false,
    currentScreen: 'home',
    meetingStartTime: null,
    currentSessionId: null,
    transcriptLog: [],
    actionsLog: [],
    actionNewCount: 0,
    currentLineEl: null,
    currentLineText: '',
    lastFragTime: 0,
    lastVisionResult: null,
    currentSentiment: 'neutral',
    faceDetector: null,
    faceTrackInterval: null,
    smoothBox: null,
    currentDocument: {
      title: 'Product Launch Marketing Brief',
      content: '',
      status: 'DRAFT',
    },
  };

  const contracts = {
    wsTypes: new Set(['transcript', 'interim', 'status', 'sentiment', 'action', 'done', 'pipeline']),
    actionTypes: new Set(['slack', 'calendar', 'task', 'document']),
  };

  const sentimentConfig = {
    positive: { icon: 'mood', borderClass: 'border-success/50', bgClass: 'bg-success/10', textClass: 'text-success' },
    happiness: { icon: 'mood', borderClass: 'border-success/50', bgClass: 'bg-success/10', textClass: 'text-success' },
    neutral: { icon: 'sentiment_neutral', borderClass: 'border-slate-500/50', bgClass: 'bg-slate-500/10', textClass: 'text-slate-400' },
    negative: { icon: 'mood_bad', borderClass: 'border-danger/50', bgClass: 'bg-danger/10', textClass: 'text-danger' },
    sadness: { icon: 'mood_bad', borderClass: 'border-purple-500/50', bgClass: 'bg-purple-500/10', textClass: 'text-purple-400' },
    anger: { icon: 'mood_bad', borderClass: 'border-danger/50', bgClass: 'bg-danger/10', textClass: 'text-danger' },
    surprise: { icon: 'warning', borderClass: 'border-warning/50', bgClass: 'bg-warning/10', textClass: 'text-warning' },
    uncertain: { icon: 'warning', borderClass: 'border-warning/50', bgClass: 'bg-warning/10', textClass: 'text-warning' },
  };

  const overlayColors = {
    happiness: '#22c55e',
    neutral: '#94a3b8',
    sadness: '#a855f7',
    anger: '#ef4444',
    surprise: '#eab308',
  };

  const actionBadge = {
    slack: { label: 'Slack', colorClasses: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
    calendar: { label: 'Calendar', colorClasses: 'bg-success/15 text-success border-success/30' },
    task: { label: 'Task', colorClasses: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
    document: { label: 'Document', colorClasses: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
    email: { label: 'Email Summary', colorClasses: 'bg-teal-500/15 text-teal-400 border-teal-500/30' },
  };

  function timeStr() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function float32ToInt16(f32) {
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const clamped = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
    }
    return i16;
  }

  function computeRms(f32) {
    let sum = 0;
    for (let i = 0; i < f32.length; i++) sum += f32[i] * f32[i];
    return Math.sqrt(sum / f32.length);
  }

  function generateSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return `meeting-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function ensureSessionId() {
    if (!state.currentSessionId) {
      state.currentSessionId = generateSessionId();
    }
    return state.currentSessionId;
  }

  function resetSessionId() {
    state.currentSessionId = null;
  }

  function sessionQuery() {
    return state.currentSessionId ? `?session_id=${encodeURIComponent(state.currentSessionId)}` : '';
  }

  try {
    if ('FaceDetector' in window) {
      state.faceDetector = new FaceDetector({ fastMode: true, maxDetectedFaces: 1 });
    }
  } catch (error) {
    console.warn('FaceDetector API not available, falling back to server-side detection');
  }

  window.MeetingAgent.core = {
    dom,
    state,
    contracts,
    sentimentConfig,
    overlayColors,
    actionBadge,
    timeStr,
    float32ToInt16,
    computeRms,
    ensureSessionId,
    resetSessionId,
    sessionQuery,
  };
})();
