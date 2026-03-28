# Frontend Design Guide — Animated Architecture Pipeline

This guide captures the visual design system and canvas animation patterns used in the Meeting Agent UI. Use it to recreate the same aesthetic with different backend nodes/edges for a new project.

---

## Stack

- **Tailwind CSS** (CDN) with custom color config
- **Material Symbols Outlined** (Google Fonts icon font)
- **Inter** (display/UI) + **Roboto Mono** (monospace/data)
- **HTML5 Canvas** for the animated pipeline diagram
- Vanilla JS — no framework required

---

## 1. Color System

Configure Tailwind with this palette. These map to semantic roles used everywhere in the UI.

```html
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<script>
  tailwind.config = {
    darkMode: "class",
    theme: {
      extend: {
        colors: {
          "primary":      "#57abff",  // blue — main data flow, CTAs
          "success":      "#3fb950",  // green — positive states, complete
          "danger":       "#f85149",  // red — errors, stop, blocked
          "warning":      "#e3b341",  // yellow — processing, uncertain
          "bg-dark":      "#0d1117",  // page background
          "surface":      "#161b22",  // cards, panels, sidebars
          "border-muted": "#30363d",  // dividers, inactive borders
          "text-main":    "#c9d1d9",  // primary text
          "text-muted":   "#8b949e",  // secondary/label text
        },
        fontFamily: {
          "display": ["Inter", "sans-serif"],
          "mono":    ["Roboto Mono", "SFMono-Regular", "Menlo", "monospace"],
        },
      },
    },
  }
</script>
```

### Node colors (for the canvas pipeline)

Assign colors to node groups by role:

| Role | Color | Hex |
|---|---|---|
| Primary flow (input → processing) | Blue | `#57abff` |
| Secondary/context feed | Purple | `#a855f7` |
| Central AI/processing hub | Yellow/amber | `#e3b341` |
| Success/completion outputs | Green | `#3fb950` |

---

## 2. Font + Icon Setup

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet" />
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
```

```css
body { font-family: 'Inter', sans-serif; }
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}
```

Use `<span class="material-symbols-outlined">icon_name</span>` for icons. Browse at [fonts.google.com/icons](https://fonts.google.com/icons).

---

## 3. Global Layout

```html
<html class="dark">
<body class="bg-bg-dark text-text-main font-display antialiased">
  <div class="flex flex-col min-h-[100dvh] max-w-5xl mx-auto w-full border-x border-border-muted bg-bg-dark">
    <!-- screens go here -->
  </div>
</body>
```

- Single centered column, max `64rem` wide
- Full-height layout using `min-h-[100dvh]`
- Left/right border to frame the content on wide viewports

---

## 4. Header / Nav Bar

```html
<header class="flex items-center justify-between h-12 px-4 border-b border-border-muted bg-surface/50 backdrop-blur-md sticky top-0 z-10">
  <h1 class="text-sm font-bold tracking-tight text-white">App Name</h1>
  <!-- status chip -->
  <div class="flex items-center gap-1.5 px-2 py-0.5 rounded border border-border-muted bg-bg-dark text-[10px] text-slate-400 font-mono uppercase tracking-wider">
    <span class="material-symbols-outlined text-[12px]">settings_input_antenna</span>
    v1.0.0
  </div>
</header>
```

Key effects: `backdrop-blur-md` (glassmorphism), `bg-surface/50` (semi-transparent), `sticky top-0`.

---

## 5. CSS Animations

Add to your `<style>` block:

```css
/* Card slide-in for dynamically appended items */
@keyframes slideIn {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.card-enter { animation: slideIn 0.25s ease-out; }

/* Pulsing indicator dot */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
.pulse-dot { animation: pulse-dot 1.5s ease-in-out infinite; }
```

Usage:
```html
<!-- Append .card-enter to new cards via JS: el.classList.add('card-enter') -->
<div class="flex items-center gap-1.5">
  <span class="pulse-dot inline-block w-1.5 h-1.5 rounded-full bg-success"></span>
  Processing...
</div>
```

### Custom scrollbar (optional)
```css
#my-scroll-area::-webkit-scrollbar { width: 5px; }
#my-scroll-area::-webkit-scrollbar-track { background: transparent; }
#my-scroll-area::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
```

---

## 6. Pipeline Canvas — Architecture Diagram

This is the core visual element: an animated node-graph rendered on an HTML5 Canvas. Nodes represent components in your system; edges show data flow; particles animate along edges when data is moving.

### HTML

```html
<!-- Container: fixed width, full height, dark background -->
<div id="pipeline-panel" class="w-[320px] flex-shrink-0 flex items-center justify-center bg-bg-dark relative border-r border-border-muted">
  <canvas id="pipeline-canvas" class="w-full h-full"></canvas>
</div>
```

### Node definition

Nodes use **normalized coordinates** (0–1) so the layout scales with any canvas size. Replace ids/labels/icons/colors with your own components.

```js
const NODES = [
  // { id, x, y, label, icon (Material Symbol name), color, size (optional, default 1), activeUntil, stats }
  { id: 'input',     x: 0.08, y: 0.30, label: 'Input',     icon: 'input',       color: '#57abff', activeUntil: 0, stats: {} },
  { id: 'processor', x: 0.48, y: 0.50, label: 'Processor', icon: 'psychology',  color: '#e3b341', size: 1.4, activeUntil: 0, stats: {} },
  { id: 'output_a',  x: 0.88, y: 0.25, label: 'Output A',  icon: 'output',      color: '#3fb950', activeUntil: 0, stats: {} },
  // ... add more
];
```

### Edge definition

```js
const EDGES = [
  // weight: 'primary' = solid line | 'informing' = dashed, thinner
  { from: 'input',     to: 'processor', weight: 'primary',   activeUntil: 0 },
  { from: 'processor', to: 'output_a',  weight: 'primary',   activeUntil: 0 },
  // ...
];
```

### Full canvas engine

Drop this into your JS. It handles: DPR-aware sizing, ResizeObserver, the animation loop, node/edge/particle drawing, and a public `activate(event)` API.

```js
(() => {
  // ── Helpers ──
  function nodeById(id) { return NODES.find(n => n.id === id); }
  function edgeKey(from, to) { return from + '->' + to; }

  // ── Canvas state ──
  let canvas, ctx, canvasW = 0, canvasH = 0, dpr = 1;

  function initCanvas() {
    canvas = document.getElementById('pipeline-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    dpr = window.devicePixelRatio || 1;

    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (!width || !height) return;
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

    const r = canvas.parentElement.getBoundingClientRect();
    if (r.width && r.height) {
      canvasW = r.width; canvasH = r.height;
      canvas.width = canvasW * dpr; canvas.height = canvasH * dpr;
      canvas.style.width = canvasW + 'px'; canvas.style.height = canvasH + 'px';
      ctx.scale(dpr, dpr);
    }
  }

  // ── Coordinate helpers ──
  function px(node) { return { x: node.x * canvasW, y: node.y * canvasH }; }

  function bezierPoint(x0, y0, cx, cy, x1, y1, t) {
    const u = 1 - t;
    return { x: u*u*x0 + 2*u*t*cx + t*t*x1, y: u*u*y0 + 2*u*t*cy + t*t*y1 };
  }

  function edgeCP(src, tgt) {
    return { x: (src.x + tgt.x) / 2, y: (src.y + tgt.y) / 2 - 30 };
  }

  // ── Draw edge ──
  function drawEdge(edge, time) {
    const src = px(nodeById(edge.from));
    const tgt = px(nodeById(edge.to));
    const cp = edgeCP(src, tgt);
    const isPrimary = edge.weight === 'primary';
    const isActive = edge.activeUntil > time;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(src.x, src.y);
    ctx.quadraticCurveTo(cp.x, cp.y, tgt.x, tgt.y);

    if (isPrimary) {
      ctx.lineWidth = isActive ? 3 : 2;
      ctx.strokeStyle = isActive ? '#57abff' : '#30363d';
      ctx.setLineDash([]);
    } else {
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

  // ── Draw node ──
  function drawNode(node, time) {
    const pos = px(node);
    const r = 24 * (node.size || 1);
    const isActive = node.activeUntil > time;
    const breathe = 0.03 * Math.sin(time * 0.5); // ambient breathing

    ctx.save();

    // Glow for active nodes
    if (isActive) {
      ctx.shadowColor = node.color;
      ctx.shadowBlur = 12 + 8 * Math.sin(time * 4); // 4Hz pulse
    }

    // Circle fill + stroke
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
    if (isActive) {
      ctx.fillStyle = node.color + '40'; // 25% opacity fill
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 2.5;
    } else {
      ctx.fillStyle = '#161b22';
      const alpha = Math.round((0.19 + breathe) * 255).toString(16).padStart(2, '0');
      ctx.strokeStyle = '#30363d' + alpha;
      ctx.lineWidth = 1.5;
    }
    ctx.fill();
    ctx.stroke();

    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;

    // Icon (Material Symbol via font)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = '18px "Material Symbols Outlined"';
    ctx.fillStyle = isActive ? node.color : '#c9d1d9';
    ctx.fillText(node.icon, pos.x, pos.y + 2);

    // Label
    ctx.font = '600 10px Inter, sans-serif';
    ctx.fillStyle = '#c9d1d9';
    ctx.textBaseline = 'top';
    ctx.fillText(node.label, pos.x, pos.y + r + 8);

    // Optional stat text
    if (node.statText) {
      ctx.font = '400 10px "Roboto Mono", monospace';
      ctx.fillStyle = '#8b949e';
      ctx.fillText(node.statText, pos.x, pos.y + r + 20);
    }

    ctx.restore();
  }

  // ── Particle system ──
  const particles = [];

  function spawnParticles(ek, color) {
    const edge = EDGES.find(e => edgeKey(e.from, e.to) === ek);
    if (!edge) return;
    const count = 3 + Math.floor(Math.random() * 3); // 3–5
    for (let i = 0; i < count; i++) {
      particles.push({
        edge: ek, from: edge.from, to: edge.to,
        t: -i * 0.05,   // stagger start
        color,
        speed: 0.008 + Math.random() * 0.004,
      });
    }
  }

  function updateParticles(dt) {
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.t += p.speed * dt * 60; // frame-rate independent
      if (p.t >= 1) { particles.splice(i, 1); continue; }
      if (p.t < 0) continue;

      const src = px(nodeById(p.from));
      const tgt = px(nodeById(p.to));
      const cp = edgeCP(src, tgt);
      const pos = bezierPoint(src.x, src.y, cp.x, cp.y, tgt.x, tgt.y, p.t);

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
  let animId = null, lastTime = 0;

  function animate(now) {
    animId = requestAnimationFrame(animate);
    const dt = Math.min((now - lastTime) / 1000, 0.1);
    lastTime = now;
    const time = now / 1000;

    if (!ctx || !canvasW || !canvasH) return;
    ctx.clearRect(0, 0, canvasW, canvasH);

    EDGES.forEach(e => drawEdge(e, time));      // Layer 1: edges
    updateParticles(dt);                         // Layer 2: particles
    NODES.forEach(n => drawNode(n, time));       // Layer 3: nodes
  }

  function start() {
    if (animId) return;
    initCanvas();
    lastTime = performance.now();
    animId = requestAnimationFrame(animate);
  }

  function stop() {
    if (animId) { cancelAnimationFrame(animId); animId = null; }
  }

  // ── Public event trigger ──
  // Call this from your backend event handler to animate a flow through the graph.
  // eventMap keys are your event names; values list which nodes/edges to activate.
  const EVENT_MAP = {
    // Example — replace with your own events:
    'data_received':  { nodes: [{ id: 'input',     dur: 1.0 }], edges: ['input->processor'] },
    'processing':     { nodes: [{ id: 'processor', dur: 2.0 }], edges: [] },
    'result_ready':   { nodes: [{ id: 'processor', dur: 1.5 }], edges: ['processor->output_a'] },
  };

  function handleEvent(data) {
    if (!data?.event) return;
    const now = performance.now() / 1000;
    const mapping = EVENT_MAP[data.event];
    if (!mapping) return;

    mapping.nodes.forEach(({ id, dur }) => {
      const n = nodeById(id);
      if (n) n.activeUntil = now + dur;
    });

    mapping.edges.forEach(ek => {
      const edge = EDGES.find(e => edgeKey(e.from, e.to) === ek);
      if (edge) {
        edge.activeUntil = now + 2.0;
        spawnParticles(ek, nodeById(edge.from)?.color || '#57abff');
      }
    });

    start(); // auto-start if not already running
  }

  // Wait for icon font before starting (avoids blank frames)
  document.fonts.ready.then(start);

  // Export
  window.MyPipeline = { handleEvent, start, stop };
})();
```

---

## 7. Status / Badge Components

### Status chip (header)
```html
<div class="flex items-center gap-1.5 px-2 py-0.5 rounded border border-border-muted bg-bg-dark text-[10px] text-slate-400 font-mono uppercase tracking-wider">
  <span class="material-symbols-outlined text-[12px]">circle</span>
  <span>Idle</span>
</div>
```

### Semantic pill (colored by state)
```html
<!-- success variant -->
<div class="flex items-center gap-1.5 px-2 py-0.5 rounded border border-success/50 bg-success/10 text-[10px] text-success font-mono uppercase tracking-wider">
  <span class="material-symbols-outlined text-[12px]">check_circle</span>
  Active
</div>
<!-- danger variant: border-danger/50 bg-danger/10 text-danger -->
<!-- warning variant: border-warning/50 bg-warning/10 text-warning -->
```

### Action type badge (inline tag)
```html
<!-- Swap colors per type: blue/green/purple/amber/teal -->
<span class="px-1.5 py-0.5 rounded border text-[10px] font-bold bg-blue-500/15 text-blue-400 border-blue-500/30">Slack</span>
<span class="px-1.5 py-0.5 rounded border text-[10px] font-bold bg-success/15 text-success border-success/30">Calendar</span>
<span class="px-1.5 py-0.5 rounded border text-[10px] font-bold bg-purple-500/15 text-purple-400 border-purple-500/30">Task</span>
<span class="px-1.5 py-0.5 rounded border text-[10px] font-bold bg-amber-500/15 text-amber-400 border-amber-500/30">Document</span>
```

---

## 8. Feature / Info List

```html
<div class="space-y-8 w-full">
  <div class="flex gap-4">
    <div class="flex-shrink-0 size-10 rounded-lg bg-surface border border-border-muted flex items-center justify-center">
      <span class="material-symbols-outlined text-primary">icon_name</span>
    </div>
    <div>
      <h3 class="text-sm font-bold text-white">Feature Title</h3>
      <p class="text-xs text-slate-400 mt-1">One-liner description of what this does.</p>
    </div>
  </div>
  <!-- repeat -->
</div>
```

---

## 9. Primary CTA Button

```html
<button class="w-full h-14 bg-success hover:bg-success/90 text-white font-bold rounded-xl shadow-lg shadow-success/20 transition-all flex items-center justify-center gap-2">
  <span class="material-symbols-outlined">play_circle</span>
  Start
</button>
```

For destructive/stop actions:
```html
<button class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-danger/10 border border-danger/30 text-danger text-xs font-bold hover:bg-danger/20 transition-colors">
  <span class="material-symbols-outlined text-sm">stop_circle</span>
  Stop
</button>
```

---

## 10. Panel / Section Layout Pattern

The three-column meeting view pattern:

```html
<div class="flex flex-1 overflow-hidden">

  <!-- Fixed-width left panel (e.g. pipeline canvas) -->
  <div class="w-[320px] flex-shrink-0 bg-bg-dark border-r border-border-muted flex items-center justify-center">
    <canvas id="pipeline-canvas" class="w-full h-full"></canvas>
  </div>

  <!-- Flexible center panel (main content / feed) -->
  <div class="flex-1 flex flex-col border-r border-border-muted min-h-0">
    <div class="flex items-center px-4 py-2 border-b border-border-muted bg-surface">
      <h2 class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Section Title</h2>
    </div>
    <div class="flex-1 overflow-y-auto p-4 bg-bg-dark"></div>
  </div>

  <!-- Fixed-width right sidebar -->
  <div class="w-64 flex flex-col bg-surface min-h-0">
    <div class="flex items-center px-4 py-2 border-b border-border-muted">
      <h2 class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Sidebar</h2>
    </div>
    <div class="flex-1 overflow-y-auto p-3 space-y-2"></div>
  </div>

</div>
```

---

## 11. Dynamic Card (appended via JS)

```js
function createCard(data) {
  const el = document.createElement('div');
  el.className = 'card-enter rounded-lg border border-border-muted bg-surface p-3';
  el.innerHTML = `
    <div class="flex items-start gap-2">
      <span class="material-symbols-outlined text-primary text-lg mt-0.5">info</span>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xs font-bold text-white truncate">${data.title}</span>
          <span class="px-1.5 py-0.5 rounded border text-[10px] font-bold bg-primary/15 text-primary border-primary/30">${data.type}</span>
        </div>
        <p class="text-xs text-slate-400 leading-relaxed">${data.description}</p>
        <p class="text-[10px] text-slate-500 mt-1 font-mono">${data.timestamp}</p>
      </div>
    </div>
  `;
  container.prepend(el);
}
```

---

## 12. Key Design Principles

1. **Dark-first**: All colors are calibrated for `#0d1117` backgrounds. Never mix in light-mode values.
2. **Semantic color usage**: Blue = data/primary flow. Green = success/complete. Red = error/stop. Yellow = processing/uncertain. Purple = secondary/context.
3. **Opacity layering**: Use `/10`–`/20` for backgrounds, `/30`–`/50` for borders, full for text. This maintains depth without contrast issues.
4. **Monospace for data**: Use `font-mono` on all live/dynamic values — counts, timestamps, IDs, status strings.
5. **Uppercase micro-labels**: Section headers at `text-[10px] uppercase tracking-widest text-slate-500` — never compete with content.
6. **Canvas layering order**: edges (back) → particles (middle) → nodes (front). Draw order matters.
7. **Font readiness**: Always wait for `document.fonts.ready` before starting the canvas loop to avoid blank icon frames.
8. **DPR scaling**: Always scale canvas by `window.devicePixelRatio` for crisp rendering on retina displays.
