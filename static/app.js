window.MeetingAgent = window.MeetingAgent || {};

(() => {
  if (!window.MeetingAgent.core || !window.MeetingAgent.render || !window.MeetingAgent.media || !window.MeetingAgent.documents || !window.MeetingAgent.session) {
    throw new Error('Meeting Agent modules failed to load');
  }

  window.MeetingAgent.documents.init();
  window.MeetingAgent.session.init();
  window.MeetingAgent.documents.loadDocumentWidget();

  // Document sidebar collapse/expand toggle
  const toggleBtn = document.getElementById('doc-sidebar-toggle');
  const sidebarBody = document.getElementById('doc-sidebar-body');
  const chevron = document.getElementById('doc-sidebar-chevron');
  if (toggleBtn && sidebarBody && chevron) {
    toggleBtn.addEventListener('click', () => {
      const expanded = !sidebarBody.classList.contains('hidden');
      if (expanded) {
        sidebarBody.classList.add('hidden');
        sidebarBody.classList.remove('flex');
        chevron.textContent = 'expand_more';
      } else {
        sidebarBody.classList.remove('hidden');
        sidebarBody.classList.add('flex');
        chevron.textContent = 'expand_less';
      }
    });
  }
})();
