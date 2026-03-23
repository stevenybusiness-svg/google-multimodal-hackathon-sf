window.MeetingAgent = window.MeetingAgent || {};

/**
 * Pipeline visualization module (stub).
 * Plan 01.5-02 implements the full Canvas renderer.
 * This stub receives pipeline events and will be replaced.
 */
(() => {
  const { core } = window.MeetingAgent;
  const { dom } = core;

  function handlePipelineEvent(data) {
    if (!data || !data.event) return;

    // Hide empty state on first event
    if (dom.pipelineEmptyState) {
      dom.pipelineEmptyState.classList.add('hidden');
    }
  }

  window.MeetingAgent.pipeline = {
    handlePipelineEvent,
  };
})();
