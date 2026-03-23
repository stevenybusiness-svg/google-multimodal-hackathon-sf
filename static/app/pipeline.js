window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core } = window.MeetingAgent;
  const { dom } = core;

  // ── Node definitions (normalized 0-1 coordinates) ──
  const NODES = [
    { id: 'mic',        x: 0.08, y: 0.30, label: 'Mic',      icon: 'mic',         color: '#57abff', activeUntil: 0, stats: {} },
    { id: 'stt',        x: 0.25, y: 0.30, label: 'STT',      icon: 'hearing',     color: '#57abff', activeUntil: 0, stats: {} },
    { id: 'camera',     x: 0.08, y: 0.70, label: 'Camera',   icon: 'videocam',    color: '#a855f7', activeUntil: 0, stats: {} },
    { id: 'vision',     x: 0.25, y: 0.70, label: 'Vision',   icon: 'visibility',  color: '#a855f7', activeUntil: 0, stats: {} },
    { id: 'gemini',     x: 0.48, y: 0.50, label: 'Gemini',   icon: 'psychology',  color: '#e3b341', size: 1.4, activeUntil: 0, stats: {} },
    { id: 'dispatcher', x: 0.68, y: 0.50, label: 'Dispatch', icon: 'call_split',  color: '#57abff', activeUntil: 0, stats: {} },
    { id: 'slack',      x: 0.88, y: 0.25, label: 'Slack',    icon: 'tag',         color: '#57abff', activeUntil: 0, stats: {} },
    { id: 'calendar',   x: 0.88, y: 0.50, label: 'Calendar', icon: 'event',       color: '#3fb950', activeUntil: 0, stats: {} },
    { id: 'tasklog',    x: 0.88, y: 0.75, label: 'Tasks',    icon: 'task_alt',    color: '#a855f7', activeUntil: 0, stats: {} },
  ];

  // ── Edge definitions ──
  const EDGES = [
    { from: 'mic',        to: 'stt',        weight: 'primary',   activeUntil: 0 },
    { from: 'stt',        to: 'gemini',     weight: 'primary',   activeUntil: 0 },
    { from: 'camera',     to: 'vision',     weight: 'informing', activeUntil: 0 },
    { from: 'vision',     to: 'gemini',     weight: 'informing', activeUntil: 0 },
    { from: 'gemini',     to: 'dispatcher', weight: 'primary',   activeUntil: 0 },
    { from: 'dispatcher', to: 'slack',      weight: 'primary',   activeUntil: 0 },
    { from: 'dispatcher', to: 'calendar',   weight: 'primary',   activeUntil: 0 },
    { from: 'dispatcher', to: 'tasklog',    weight: 'primary',   activeUntil: 0 },
  ];

  // ── Helpers ──
  function nodeById(id) {
    return NODES.find(function (n) { return n.id === id; });
  }

  function edgeKey(from, to) {
    return from + '->' + to;
  }

  // ── Canvas state ──
  let canvas = null;
  let ctx = null;
  let canvasW = 0;
  let canvasH = 0;
  let dpr = 1;

  function initCanvas() {
    canvas = dom.pipelineCanvas;
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    dpr = window.devicePixelRatio || 1;

    const observer = new ResizeObserver(function (entries) {
      const rect = entries[0].contentRect;
      const width = rect.width;
      const height = rect.height;
      if (width === 0 || height === 0) return;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = width + 'px';
      canvas.style.height = height + 'px';
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
      canvasW = width;
      canvasH = height;
    });
    observer.observe(canvas.parentElement);

    // Initial size
    const parentRect = canvas.parentElement.getBoundingClientRect();
    if (parentRect.width > 0 && parentRect.height > 0) {
      canvasW = parentRect.width;
      canvasH = parentRect.height;
      canvas.width = canvasW * dpr;
      canvas.height = canvasH * dpr;
      canvas.style.width = canvasW + 'px';
      canvas.style.height = canvasH + 'px';
      ctx.scale(dpr, dpr);
    }
  }

  // ── Coordinate scaling ──
  function px(node) {
    return { x: node.x * canvasW, y: node.y * canvasH };
  }

  // ── Bezier point helper ──
  function bezierPoint(x0, y0, cx, cy, x1, y1, t) {
    var u = 1 - t;
    return {
      x: u * u * x0 + 2 * u * t * cx + t * t * x1,
      y: u * u * y0 + 2 * u * t * cy + t * t * y1,
    };
  }

  // ── Edge control point helper ──
  function edgeControlPoint(src, tgt) {
    return {
      x: (src.x + tgt.x) / 2,
      y: (src.y + tgt.y) / 2 - 30,
    };
  }

  // ── Draw edge ──
  function drawEdge(ctx, edge, time) {
    var srcNode = nodeById(edge.from);
    var tgtNode = nodeById(edge.to);
    if (!srcNode || !tgtNode) return;
    var src = px(srcNode);
    var tgt = px(tgtNode);
    var cp = edgeControlPoint(src, tgt);

    var isPrimary = edge.weight === 'primary';
    var isActive = edge.activeUntil > time;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(src.x, src.y);
    ctx.quadraticCurveTo(cp.x, cp.y, tgt.x, tgt.y);

    if (isPrimary) {
      ctx.lineWidth = isActive ? 3 : 2;
      ctx.strokeStyle = isActive ? '#57abff' : '#30363d';
      ctx.setLineDash([]);
    } else {
      // Informing edge: thinner, dashed
      ctx.lineWidth = isActive ? 1.5 : 1;
      ctx.strokeStyle = isActive ? '#a855f780' : '#30363d99';
      ctx.setLineDash([4, 4]);
    }

    if (isActive) {
      ctx.shadowColor = isPrimary ? '#57abff' : '#a855f7';
      ctx.shadowBlur = 6;
    }

    ctx.stroke();
    ctx.restore();
  }

  // ── Node stat text helper ──
  function getStatText(node) {
    var s = node.stats;
    switch (node.id) {
      case 'stt': return s.words ? s.words + ' words' : '';
      case 'vision': return s.sentiment ? s.sentiment + ' ' + (s.score || '') : '';
      case 'gemini': return s.actions ? s.actions + ' actions' : '';
      case 'dispatcher': return s.fired ? s.fired + ' fired' : '';
      case 'slack':
      case 'calendar':
      case 'tasklog':
        return s.count ? '' + s.count : '';
      default: return '';
    }
  }

  // ── Draw node ──
  function drawNode(ctx, node, time) {
    var pos = px(node);
    var baseRadius = 24 * (node.size || 1);
    var isActive = node.activeUntil > time;

    // Ambient breathing for all nodes: border opacity modulates +/- 3%
    var breathe = 0.03 * Math.sin(time * 0.5);

    ctx.save();

    // Glow effect for active nodes
    if (isActive) {
      var pulse = Math.sin(time * 4); // 4 Hz pulse
      ctx.shadowColor = node.color;
      ctx.shadowBlur = 12 + 8 * pulse;
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, baseRadius, 0, Math.PI * 2);

    if (isActive) {
      ctx.fillStyle = node.color + '40'; // 25% opacity
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 2.5;
    } else {
      ctx.fillStyle = '#161b22';
      // Apply breathing to border opacity
      var borderAlpha = Math.round((0.19 + breathe) * 255).toString(16).padStart(2, '0');
      ctx.strokeStyle = '#30363d' + borderAlpha;
      ctx.lineWidth = 1.5;
    }
    ctx.fill();
    ctx.stroke();

    // Reset shadow after circle
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;

    // Icon (Material Symbols Outlined)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = '18px Material Symbols Outlined';
    ctx.fillStyle = isActive ? node.color : '#c9d1d9';
    ctx.fillText(node.icon, pos.x, pos.y + 2);

    // Label below circle
    ctx.font = '600 10px Inter, sans-serif';
    ctx.fillStyle = '#c9d1d9';
    ctx.textBaseline = 'top';
    ctx.fillText(node.label, pos.x, pos.y + baseRadius + 8);

    // Stats below label
    var statText = getStatText(node);
    if (statText) {
      ctx.font = '400 10px Roboto Mono, monospace';
      ctx.fillStyle = '#8b949e';
      ctx.fillText(statText, pos.x, pos.y + baseRadius + 20);
    }

    ctx.restore();
  }

  // ── Particle system ──
  var particles = [];

  function spawnParticles(ek, color) {
    var edge = EDGES.find(function (e) { return edgeKey(e.from, e.to) === ek; });
    if (!edge) return;
    var count = 3 + Math.floor(Math.random() * 3); // 3-5 particles
    for (var i = 0; i < count; i++) {
      particles.push({
        edge: ek,
        from: edge.from,
        to: edge.to,
        t: -i * 0.05, // stagger start
        color: color,
        speed: 0.008 + Math.random() * 0.004,
      });
    }
  }

  function updateAndDrawParticles(ctx, dt, time) {
    for (var i = particles.length - 1; i >= 0; i--) {
      var p = particles[i];
      // Frame-rate independent speed
      p.t += p.speed * dt * 60;

      if (p.t >= 1) {
        particles.splice(i, 1);
        continue;
      }
      if (p.t < 0) continue; // staggered start

      var srcNode = nodeById(p.from);
      var tgtNode = nodeById(p.to);
      if (!srcNode || !tgtNode) { particles.splice(i, 1); continue; }

      var src = px(srcNode);
      var tgt = px(tgtNode);
      var cp = edgeControlPoint(src, tgt);
      var pos = bezierPoint(src.x, src.y, cp.x, cp.y, tgt.x, tgt.y, p.t);

      ctx.save();
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.shadowColor = p.color;
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.restore();
    }
  }

  // ── Animation loop ──
  var animationId = null;
  var lastTime = 0;

  function animate(currentTime) {
    animationId = requestAnimationFrame(animate);
    var dt = Math.min((currentTime - lastTime) / 1000, 0.1); // clamp to 100ms
    lastTime = currentTime;
    var time = currentTime / 1000;

    if (!ctx || canvasW === 0 || canvasH === 0) return;

    ctx.clearRect(0, 0, canvasW, canvasH);

    // Layer 1: Edges (back)
    for (var i = 0; i < EDGES.length; i++) {
      drawEdge(ctx, EDGES[i], time);
    }
    // Layer 2: Particles (middle)
    updateAndDrawParticles(ctx, dt, time);
    // Layer 3: Nodes (front)
    for (var j = 0; j < NODES.length; j++) {
      drawNode(ctx, NODES[j], time);
    }
  }

  // ── Public API: start / stop ──
  function startAnimation() {
    if (animationId) return;
    initCanvas();
    lastTime = performance.now();
    animationId = requestAnimationFrame(animate);
  }

  function stopAnimation() {
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
  }

  // ── Pipeline event mapping ──
  var EVENT_MAP = {
    'stt_start':            { nodes: [{ id: 'mic', dur: 1.0 }], edges: ['mic->stt'] },
    'stt_result':           { nodes: [{ id: 'stt', dur: 1.5 }], edges: ['stt->gemini'] },
    'understanding_start':  { nodes: [{ id: 'gemini', dur: 2.0 }], edges: [] },
    'understanding_result': { nodes: [{ id: 'gemini', dur: 2.0 }], edges: ['gemini->dispatcher'] },
    'vision_result':        { nodes: [{ id: 'camera', dur: 1.0 }, { id: 'vision', dur: 1.5 }], edges: ['camera->vision', 'vision->gemini'] },
    'action_dispatched':    { nodes: [{ id: 'dispatcher', dur: 1.0 }], edges: [] },
  };

  function handlePipelineEvent(data) {
    if (!data || !data.event) return;
    var now = performance.now() / 1000;
    var mapping = EVENT_MAP[data.event];
    if (!mapping) return;

    // Hide empty state on first event
    var emptyState = dom.pipelineEmptyState;
    if (emptyState) emptyState.style.display = 'none';

    // Activate nodes
    for (var i = 0; i < mapping.nodes.length; i++) {
      var entry = mapping.nodes[i];
      var node = nodeById(entry.id);
      if (node) node.activeUntil = now + entry.dur;
    }

    // Activate edges + spawn particles
    for (var j = 0; j < mapping.edges.length; j++) {
      var ek = mapping.edges[j];
      var edge = EDGES.find(function (e) { return edgeKey(e.from, e.to) === ek; });
      if (edge) {
        edge.activeUntil = now + 2.0;
        var srcNode = nodeById(edge.from);
        spawnParticles(ek, srcNode ? srcNode.color : '#57abff');
      }
    }

    // Handle action_dispatched: dynamic edge based on action_type
    if (data.event === 'action_dispatched' && data.action_type) {
      var targetMap = { slack: 'slack', calendar: 'calendar', task: 'tasklog', document: 'slack' };
      var target = targetMap[data.action_type] || 'tasklog';
      var dispEk = 'dispatcher->' + target;
      var dispEdge = EDGES.find(function (e) { return edgeKey(e.from, e.to) === dispEk; });
      if (dispEdge) {
        dispEdge.activeUntil = now + 2.0;
        spawnParticles(dispEk, '#57abff');
      }
      var targetNode = nodeById(target);
      if (targetNode) {
        targetNode.activeUntil = now + 1.0;
        targetNode.stats.count = (targetNode.stats.count || 0) + 1;
      }
      var dispNode = nodeById('dispatcher');
      if (dispNode) dispNode.stats.fired = (dispNode.stats.fired || 0) + 1;
    }

    // Update stats from event data
    if (data.event === 'stt_result' && data.stats) {
      var sttNode = nodeById('stt');
      if (sttNode) sttNode.stats.words = (sttNode.stats.words || 0) + (data.stats.words || 0);
    }
    if (data.event === 'understanding_result' && data.stats) {
      var gemNode = nodeById('gemini');
      if (gemNode) gemNode.stats.actions = (gemNode.stats.actions || 0) + (data.stats.actions || 0);
    }
    if (data.event === 'vision_result' && data.stats) {
      var visNode = nodeById('vision');
      if (visNode) {
        visNode.stats.sentiment = data.stats.sentiment || '';
        visNode.stats.score = data.stats.score || '';
      }
    }

    // Start animation if not running
    startAnimation();
  }

  // ── Auto-start: wait for fonts then begin rendering ──
  document.fonts.ready.then(function () {
    startAnimation();
  });

  // ── Module exports ──
  window.MeetingAgent.pipeline = {
    handlePipelineEvent: handlePipelineEvent,
    startAnimation: startAnimation,
    stopAnimation: stopAnimation,
  };
})();
