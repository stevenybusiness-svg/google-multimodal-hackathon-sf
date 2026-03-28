window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core, render } = window.MeetingAgent;
  const { dom, state, computeRms, float32ToInt16, overlayColors, sessionQuery } = core;

  function lerp(a, b, amount) {
    return a + (b - a) * amount;
  }

  function videoToCanvas(box, videoWidth, videoHeight) {
    const canvasWidth = dom.visionCanvas.width;
    const canvasHeight = dom.visionCanvas.height;
    const scale = Math.max(canvasWidth / videoWidth, canvasHeight / videoHeight);
    const scaledWidth = videoWidth * scale;
    const scaledHeight = videoHeight * scale;
    const offsetX = (canvasWidth - scaledWidth) / 2;
    const offsetY = (canvasHeight - scaledHeight) / 2;
    return {
      x: box.x * scale + offsetX,
      y: box.y * scale + offsetY,
      w: (box.width || box.w) * scale,
      h: (box.height || box.h) * scale,
    };
  }

  function drawLocalFaceOverlay(box, sentiment) {
    const ctx = dom.visionCanvas.getContext('2d');
    const color = overlayColors[sentiment] || overlayColors.neutral;
    ctx.clearRect(0, 0, dom.visionCanvas.width, dom.visionCanvas.height);

    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    const radius = 6;
    ctx.moveTo(box.x + radius, box.y);
    ctx.lineTo(box.x + box.w - radius, box.y);
    ctx.arcTo(box.x + box.w, box.y, box.x + box.w, box.y + radius, radius);
    ctx.lineTo(box.x + box.w, box.y + box.h - radius);
    ctx.arcTo(box.x + box.w, box.y + box.h, box.x + box.w - radius, box.y + box.h, radius);
    ctx.lineTo(box.x + radius, box.y + box.h);
    ctx.arcTo(box.x, box.y + box.h, box.x, box.y + box.h - radius, radius);
    ctx.lineTo(box.x, box.y + radius);
    ctx.arcTo(box.x, box.y, box.x + radius, box.y, radius);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();

    const label = (sentiment || 'neutral').toUpperCase();
    ctx.font = 'bold 9px monospace';
    const metrics = ctx.measureText(label);
    const labelWidth = metrics.width + 8;
    const labelHeight = 14;
    const labelX = box.x + (box.w - labelWidth) / 2;
    const labelY = Math.max(0, box.y - labelHeight - 3);
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
      const cx = box.x + box.w / 2;
      // Down arrows on left and right of face box
      const arrowPositions = [
        { x: box.x - 14, y: box.y + box.h * 0.3 },
        { x: box.x - 14, y: box.y + box.h * 0.6 },
        { x: box.x + box.w + 6, y: box.y + box.h * 0.3 },
        { x: box.x + box.w + 6, y: box.y + box.h * 0.6 },
      ];
      for (const pos of arrowPositions) {
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y);
        ctx.lineTo(pos.x + arrowSize, pos.y);
        ctx.lineTo(pos.x + arrowSize / 2, pos.y + arrowSize);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();
    }
  }

  async function trackFaceLocal() {
    if (!state.active || !state.videoStream || !state.faceDetector) return;
    try {
      const faces = await state.faceDetector.detect(dom.visionVideo);
      const videoWidth = dom.visionVideo.videoWidth;
      const videoHeight = dom.visionVideo.videoHeight;
      if (faces.length > 0 && videoWidth && videoHeight) {
        const target = videoToCanvas(faces[0].boundingBox, videoWidth, videoHeight);
        if (state.smoothBox) {
          state.smoothBox.x = lerp(state.smoothBox.x, target.x, 0.3);
          state.smoothBox.y = lerp(state.smoothBox.y, target.y, 0.3);
          state.smoothBox.w = lerp(state.smoothBox.w, target.w, 0.3);
          state.smoothBox.h = lerp(state.smoothBox.h, target.h, 0.3);
        } else {
          state.smoothBox = { ...target };
        }
        drawLocalFaceOverlay(state.smoothBox, (state.lastVisionResult && state.lastVisionResult.sentiment) || 'neutral');
      } else {
        state.smoothBox = null;
        dom.visionCanvas.getContext('2d').clearRect(0, 0, dom.visionCanvas.width, dom.visionCanvas.height);
      }
    } catch (error) {
      console.warn('Local face tracking failed:', error);
    }
  }

  async function startVisionCapture() {
    try {
      state.videoStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      dom.visionVideo.srcObject = state.videoStream;
      await dom.visionVideo.play();
      dom.visionVideo.classList.remove('hidden');
      dom.visionVideo.style.cssText = 'display:block;position:fixed;bottom:60px;right:16px;width:200px;height:150px;border-radius:12px;border:3px solid #30363d;z-index:50;object-fit:cover;box-shadow:0 4px 16px rgba(0,0,0,0.6);transition:border-color 0.5s ease, box-shadow 0.5s ease;';
      dom.visionCanvas.classList.remove('hidden');
      dom.visionCanvas.width = 200;
      dom.visionCanvas.height = 150;
      dom.visionCanvas.style.cssText = 'display:block;position:fixed;bottom:60px;right:16px;width:200px;height:150px;border-radius:12px;z-index:51;pointer-events:none;';

      if (state.faceDetector) {
        state.faceTrackInterval = setInterval(trackFaceLocal, 100);
      }

      state.frameInterval = setInterval(async () => {
        if (!state.videoStream || !state.active) return;
        const { videoWidth, videoHeight } = dom.visionVideo;
        if (!videoWidth || !videoHeight) return;
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = videoWidth;
        tempCanvas.height = videoHeight;
        tempCanvas.getContext('2d').drawImage(dom.visionVideo, 0, 0, videoWidth, videoHeight);

        tempCanvas.toBlob(async (blob) => {
          if (!blob) return;
          try {
            const response = await fetch(`/api/frame${sessionQuery()}`, {
              method: 'POST',
              body: blob,
              headers: { 'Content-Type': 'image/jpeg' },
            });
            const result = await response.json();
            if (result && result.sentiment) {
              state.lastVisionResult = result;
              render.updateSentiment(result.sentiment);
              if (!state.faceDetector) {
                render.drawSentimentOverlay(result, videoWidth, videoHeight);
              }
            } else if (state.lastVisionResult && !state.faceDetector) {
              render.drawSentimentOverlay(state.lastVisionResult, videoWidth, videoHeight);
            }
          } catch (error) {
            console.warn('Vision frame upload failed:', error);
          }
        }, 'image/jpeg', 0.7);
      }, 3000);
    } catch (error) {
      console.warn('Vision capture unavailable:', error);
    }
  }

  async function startMedia() {
    state.micStream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
      video: false,
    });
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
      throw new Error('Connection lost during setup');
    }

    state.audioCtx = new AudioContext({ sampleRate: 16000 });
    if (state.audioCtx.sampleRate !== 16000) {
      throw new Error(`Expected 16kHz audio input, got ${state.audioCtx.sampleRate}Hz`);
    }

    const source = state.audioCtx.createMediaStreamSource(state.micStream);
    state.processor = state.audioCtx.createScriptProcessor(1024, 1, 1);
    state.processor.onaudioprocess = (event) => {
      const floats = event.inputBuffer.getChannelData(0);
      const rms = computeRms(floats);
      var micWidth = `${Math.min(rms * 400, 100).toFixed(1)}%`;
      dom.micLevel.style.width = micWidth;
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        try {
          state.ws.send(float32ToInt16(floats).buffer);
        } catch (error) {
          console.error('Audio send failed:', error);
        }
      }
    };

    source.connect(state.processor);
    state.processor.connect(state.audioCtx.destination);
    await startVisionCapture();
  }

  function stopMediaOnly() {
    clearInterval(state.frameInterval);
    clearInterval(state.faceTrackInterval);
    state.frameInterval = null;
    state.faceTrackInterval = null;
    state.smoothBox = null;

    if (state.processor) { state.processor.disconnect(); state.processor = null; }
    if (state.audioCtx) { state.audioCtx.close(); state.audioCtx = null; }
    if (state.micStream) { state.micStream.getTracks().forEach((track) => track.stop()); state.micStream = null; }
    if (state.videoStream) { state.videoStream.getTracks().forEach((track) => track.stop()); state.videoStream = null; }

    dom.visionVideo.srcObject = null;
    dom.visionVideo.classList.add('hidden');
    dom.visionVideo.style.cssText = '';
    dom.visionCanvas.getContext('2d').clearRect(0, 0, dom.visionCanvas.width, dom.visionCanvas.height);
    dom.visionCanvas.classList.add('hidden');
    dom.visionCanvas.style.cssText = '';
    state.lastVisionResult = null;
    dom.micLevel.style.width = '0%';
    dom.processingInd.classList.add('hidden');
    dom.processingInd.classList.remove('flex');
  }

  function cleanupResources() {
    stopMediaOnly();
    if (state.ws && state.ws.readyState !== WebSocket.CLOSED) {
      state.ws.close();
    }
    state.ws = null;
  }

  window.MeetingAgent.media = {
    startMedia,
    stopMediaOnly,
    cleanupResources,
  };
})();
