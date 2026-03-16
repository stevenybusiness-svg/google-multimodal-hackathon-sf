window.MeetingAgent = window.MeetingAgent || {};

(() => {
  const { core } = window.MeetingAgent;
  const { dom, state, sessionQuery } = core;

  function simpleMarkdown(markdown) {
    const lines = markdown.split('\n');
    let html = '';
    let inTable = false;
    let inUl = false;
    let inOl = false;

    function closeList() {
      if (inUl) { html += '</ul>'; inUl = false; }
      if (inOl) { html += '</ol>'; inOl = false; }
    }

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        closeList();
        if (inTable) { html += '</table>'; inTable = false; }
        continue;
      }
      if (trimmed.startsWith('## ')) {
        closeList();
        html += `<h3 class="text-sm font-bold text-white mt-4 mb-2">${trimmed.slice(3)}</h3>`;
        continue;
      }
      if (trimmed.startsWith('# ')) {
        closeList();
        html += `<h2 class="text-base font-bold text-white mb-3">${trimmed.slice(2)}</h2>`;
        continue;
      }
      if (trimmed === '---') {
        closeList();
        html += '<hr class="border-border-muted my-3">';
        continue;
      }
      if (trimmed.startsWith('|')) {
        if (trimmed.replace(/[|\-\s]/g, '') === '') continue;
        if (!inTable) { html += '<table class="w-full text-xs mb-2">'; inTable = true; }
        const cells = trimmed.split('|').filter((cell) => cell.trim());
        const isHeader = cells.some((cell) => cell.includes('**'));
        const tag = isHeader ? 'th' : 'td';
        html += '<tr>';
        cells.forEach((cell) => {
          const clean = cell.trim().replace(/\*\*/g, '');
          html += `<${tag} class="px-2 py-1 border-b border-border-muted text-left ${isHeader ? 'font-bold text-white' : 'text-slate-300'}">${clean}</${tag}>`;
        });
        html += '</tr>';
        continue;
      }
      if (trimmed.startsWith('- ')) {
        if (!inUl) {
          if (inOl) { html += '</ol>'; inOl = false; }
          html += '<ul class="space-y-1 mb-2 ml-1">';
          inUl = true;
        }
        const content = trimmed.slice(2).replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>');
        html += `<li class="text-xs text-slate-300 flex gap-1.5"><span class="text-slate-500 mt-0.5">•</span><span>${content}</span></li>`;
        continue;
      }
      if (/^\d+\.\s/.test(trimmed)) {
        if (!inOl) {
          if (inUl) { html += '</ul>'; inUl = false; }
          html += '<ol class="space-y-1 mb-2 ml-1 list-decimal list-inside">';
          inOl = true;
        }
        const content = trimmed.replace(/^\d+\.\s/, '').replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>');
        html += `<li class="text-xs text-slate-300">${content}</li>`;
        continue;
      }
      closeList();
      const processed = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>');
      html += `<p class="text-xs text-slate-300 mb-1">${processed}</p>`;
    }

    closeList();
    if (inTable) html += '</table>';
    return html;
  }

  function renderDocument() {
    dom.docWidgetContent.innerHTML = simpleMarkdown(state.currentDocument.content || '');
    dom.docModalTitle.textContent = state.currentDocument.title || 'Document';
  }

  function setDocumentContent({ title, content, status }) {
    if (title) state.currentDocument.title = title;
    if (typeof content === 'string') state.currentDocument.content = content;
    if (status) state.currentDocument.status = status;
    renderDocument();
  }

  async function loadDocumentWidget() {
    try {
      const response = await fetch(`/api/document${sessionQuery()}`);
      const data = await response.json();
      setDocumentContent({
        title: data.title || 'Document',
        content: data.content || '',
        status: data.status || 'DRAFT',
      });
    } catch (error) {
      console.warn('Failed to load document:', error);
      dom.docWidgetContent.innerHTML = '<div class="text-xs text-slate-500 text-center py-8">Failed to load document</div>';
    }
  }

  function applyAction(action) {
    if (!action || action.type !== 'document' || !action.payload) return;
    if (action.payload.content) {
      setDocumentContent({
        title: action.payload.title || state.currentDocument.title,
        content: action.payload.content,
        status: action.status === 'failed' ? 'DRAFT' : state.currentDocument.status,
      });
    }
  }

  function init() {
    dom.docExpandBtn.addEventListener('click', () => {
      dom.docModalBody.innerHTML = simpleMarkdown(state.currentDocument.content || '');
      dom.docModal.classList.remove('hidden');
    });
    dom.docModalClose.addEventListener('click', () => {
      dom.docModal.classList.add('hidden');
    });
    dom.docModal.addEventListener('click', (event) => {
      if (event.target === dom.docModal) dom.docModal.classList.add('hidden');
    });
    dom.docDownloadBtn.addEventListener('click', () => {
      const blob = new Blob([state.currentDocument.content || ''], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'marketing_brief.md';
      anchor.click();
      URL.revokeObjectURL(url);
    });
  }

  window.MeetingAgent.documents = {
    init,
    loadDocumentWidget,
    applyAction,
    setDocumentContent,
  };
})();
