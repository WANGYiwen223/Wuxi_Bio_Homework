const el = id => document.getElementById(id);
let session = null, caseId = null, pendingConsent = null, reviewSession = null, busy = false;
let caseStatus = '', pollTimer = null, pollGeneration = 0, activityCursor = 0, diagnosticCursor = 0;
let activityRows = new Map(), diagnosticEvents = [], lastMessages = '', lastSources = '', requestStarted = 0;
const statusLabels = {investigating:'Investigating', awaiting_employee:'Waiting for your reply or permission', awaiting_approval:'Waiting for manager approval', awaiting_verification:'Waiting for your feedback', resolved:'Resolved', escalated:'Handed to IT'};

async function api(path, body, review = false) {
  const token = review ? reviewSession : session;
  const r = await fetch(path, {method:body === undefined ? 'GET' : 'POST', headers:{'Content-Type':'application/json', ...(token ? {Authorization:'Bearer ' + token} : {})}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const data = await r.json();
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Request rejected');
  return data;
}
function text(tag, value, cls) {
  const n = document.createElement(tag); n.textContent = value; if (cls) n.className = cls; return n;
}
function setBusy(value) {
  busy = value;
  for (const id of ['newCase','employee','message','allow','decline','fixed','notFixed','refresh']) el(id).disabled = value;
  el('send').disabled = value || !caseId || ['awaiting_approval','awaiting_verification','resolved','escalated'].includes(caseStatus);
  el('waiting').hidden = !value;
  if (value) { requestStarted = Date.now(); el('waiting').textContent = 'Request in progress…'; }
}
function messageBody(message) {
  const body = text('div', '');
  const citations = new Map((message.citations || []).map(source => [source.number, source]));
  for (const piece of message.text.split(/(\[\d+\])/g)) {
    const number = /^\[(\d+)\]$/.exec(piece)?.[1];
    if (!number || !citations.has(Number(number))) { body.append(document.createTextNode(piece)); continue; }
    const source = citations.get(Number(number));
    const button = text('button', piece, 'citation');
    button.type = 'button'; button.setAttribute('aria-label', 'View source ' + number + ': ' + source.title);
    button.onclick = () => { const card = el('source-' + number); if (card) { card.open = true; card.scrollIntoView({block:'nearest', behavior:'smooth'}); card.focus(); } };
    body.append(button);
  }
  return body;
}
function renderCase(data) {
  const c = data.case; caseStatus = c.status;
  el('status').textContent = statusLabels[c.status] || c.status;
  el('caseInfo').textContent = data.handoff ? 'IT team: ' + data.handoff.support_group + ' · ' + data.handoff.status : 'Steps update as they run. Source times use the demo clock.';
  const serialized = JSON.stringify(data.messages);
  if (serialized !== lastMessages) {
    lastMessages = serialized; el('chat').replaceChildren();
    for (const m of data.messages) {
      const bubble = text('div', '', 'bubble ' + m.role);
      bubble.append(text('div', m.role === 'employee' ? 'You' : 'IT assistant', 'label'), messageBody(m));
      el('chat').append(bubble);
    }
    el('chat').scrollTop = el('chat').scrollHeight;
  }
  const sourceState = JSON.stringify(data.sources);
  if (sourceState !== lastSources) {
    const opened = new Set([...el('sources').querySelectorAll('details[open]')].map(node => node.id));
    lastSources = sourceState; el('sources').replaceChildren();
    for (const source of data.sources) {
      const card = text('details', '', 'source'); card.id = 'source-' + source.number; card.tabIndex = -1; card.open = opened.has(card.id);
      card.append(text('summary', '[' + source.number + '] ' + source.title));
      if (source.summary) card.append(text('p', source.summary));
      card.append(text('p', 'Source time: ' + (source.observed_at || 'unavailable') + ' · Version: ' + source.version));
      el('sources').append(card);
    }
  }
  el('facts').textContent = JSON.stringify({case_id:c.case_id, facts:c.facts, attempted_fixes:c.attempted_fixes, tool_errors:c.tool_errors, verification:c.verification, evidence:data.evidence}, null, 2);
  pendingConsent = c.facts.pending_consent;
  el('consent').style.display = pendingConsent ? 'block' : 'none';
  el('consentText').textContent = pendingConsent ? pendingConsent.explanation : '';
  el('feedback').style.display = c.status === 'awaiting_verification' || (c.status === 'awaiting_employee' && c.facts.last_response_kind === 'guidance') ? 'block' : 'none';
  el('send').disabled = busy || ['awaiting_approval','awaiting_verification','resolved','escalated'].includes(c.status);
}
async function refresh() {
  if (!caseId) return;
  const id = caseId, generation = pollGeneration;
  const data = await api('/cases/' + id);
  if (generation === pollGeneration && id === caseId) renderCase(data);
}
function renderActivity(events) {
  for (const event of events) {
    const key = event.turn_id && event.call_id ? event.turn_id + ':' + event.call_id : event.event.startsWith('turn_') ? event.turn_id : event.sequence;
    activityRows.set(key, event);
    if (['turn_completed','turn_failed'].includes(event.event)) {
      for (const [rowKey, row] of activityRows) {
        if (row.turn_id === event.turn_id && row.status === 'running') activityRows.set(rowKey, {...row, status:'interrupted'});
      }
    }
    el('activityStatus').textContent = event.label;
  }
  if (!events.length) return;
  el('activity').replaceChildren();
  for (const event of activityRows.values()) {
    const row = text('li', event.label, event.status);
    row.append(text('span', event.status + (event.duration_ms == null ? '' : ' · ' + (event.duration_ms / 1000).toFixed(1) + 's'), 'step-state'));
    el('activity').append(row);
  }
  el('activity').scrollTop = el('activity').scrollHeight;
}
async function fetchActivity(generation) {
  let more;
  do {
    const data = await api('/cases/' + caseId + '/activity?after=' + activityCursor);
    if (generation !== pollGeneration) return;
    activityCursor = data.cursor; renderActivity(data.events); more = data.has_more;
  } while (more);
  if (el('developer').open) {
    do {
      const data = await api('/cases/' + caseId + '/diagnostics?after=' + diagnosticCursor);
      if (generation !== pollGeneration) return;
      diagnosticCursor = data.cursor; diagnosticEvents.push(...data.events); more = data.has_more;
    } while (more);
    el('diagnostics').textContent = diagnosticEvents.map(event => JSON.stringify(event)).join('\n');
  }
}
async function poll(generation) {
  if (generation !== pollGeneration || !caseId) return;
  try {
    await fetchActivity(generation);
    if (generation !== pollGeneration) return;
    await refresh();
    el('activityError').textContent = '';
  } catch (_) {
    if (generation === pollGeneration) el('activityError').textContent = 'Progress updates are temporarily unavailable. Reconnecting…';
  } finally {
    if (generation === pollGeneration) {
      if (busy) el('waiting').textContent = 'Working · ' + Math.floor((Date.now() - requestStarted) / 1000) + 's elapsed. You can follow the steps in Investigation.';
      pollTimer = setTimeout(() => poll(generation), busy ? 1000 : 3000);
    }
  }
}
function resetCase() {
  clearTimeout(pollTimer); pollGeneration++; activityCursor = 0; diagnosticCursor = 0;
  activityRows = new Map(); diagnosticEvents = []; lastMessages = ''; lastSources = '';
  for (const id of ['activity','activityStatus','activityError','diagnostics','sources','facts','chat']) el(id).replaceChildren();
  poll(pollGeneration);
}
async function guarded(fn) {
  if (busy) return;
  el('error').textContent = ''; setBusy(true);
  try { await fn(); } catch (e) { el('error').textContent = e.message; }
  finally { setBusy(false); try { await refresh(); } catch (e) { el('error').textContent = e.message; } }
}
el('newCase').onclick = () => guarded(async () => {
  session = (await api('/demo/sessions', {employee_id:el('employee').value})).session_id;
  caseId = (await api('/cases', {})).case_id; resetCase();
});
el('composer').onsubmit = e => {
  e.preventDefault(); if (!caseId) { el('error').textContent = 'Start a case first.'; return; }
  const message = el('message').value.trim(); if (!message || busy) return;
  guarded(async () => {
    el('status').textContent = 'Request sent…';
    await api('/cases/' + caseId + '/messages', {text:message}); el('message').value = '';
  });
};
el('refresh').onclick = () => guarded(refresh);
async function consent(allow) {
  await api('/cases/' + caseId + '/consent', {operation:pendingConsent.operation, allow});
  await api('/cases/' + caseId + '/messages', {text:allow ? 'I provided consent through the application. Please continue.' : 'I declined the simulated action. Please offer another option or human help.'});
}
el('allow').onclick = () => guarded(() => consent(true));
el('decline').onclick = () => guarded(() => consent(false));
el('fixed').onclick = () => guarded(() => api('/cases/' + caseId + '/feedback', {resolved:true}));
el('notFixed').onclick = () => guarded(() => api('/cases/' + caseId + '/feedback', {resolved:false}));
el('reviewer').onchange = () => { reviewSession = null; };
async function loadReview() {
  if (!reviewSession) reviewSession = (await api('/demo/sessions', {employee_id:el('reviewer').value})).session_id;
  el('reviewQueue').replaceChildren();
  const list = await api('/review/approvals', undefined, true);
  for (const item of list) {
    const a = item.approval, card = text('div', '', 'card');
    card.append(text('div', a.employee_id + ' requests ' + item.action.resource_id + ' / ' + (item.action.parameters.role || '')), text('p', item.action.parameters.business_justification || ''));
    for (const [label, approve] of [['Approve',true],['Reject',false]]) {
      const b = text('button', label); b.style.marginRight = '8px';
      b.onclick = async () => { b.disabled = true; try { await api('/review/approvals/' + a.approval_id + '/decision', {approve}, true); await loadReview(); await refresh(); } catch (e) { el('reviewError').textContent = e.message; } finally { b.disabled = false; } };
      card.append(b);
    }
    el('reviewQueue').append(card);
  }
  try {
    const handoffs = await api('/review/handoffs', undefined, true);
    for (const h of handoffs) {
      const card = text('div', '', 'card'); card.append(text('div', h.support_group + ' · ' + h.status), text('p', h.issue_summary));
      const d = document.createElement('details'); d.append(text('summary', 'Full handoff'), text('pre', JSON.stringify(h, null, 2))); card.append(d);
      if (h.status === 'queued') {
        const b = text('button', 'Acknowledge');
        b.onclick = async () => { try { await api('/review/handoffs/' + h.handoff_id + '/acknowledge', {}, true); await loadReview(); await refresh(); } catch (e) { el('reviewError').textContent = e.message; } }; card.append(b);
      }
      el('reviewQueue').append(card);
    }
  } catch (_) { if (!list.length) el('reviewQueue').append(text('p', 'No specialist queue for this reviewer role.')); }
  if (!el('reviewQueue').children.length) el('reviewQueue').append(text('p', 'No pending reviews.'));
}
el('reviewRefresh').onclick = async () => { el('reviewError').textContent = ''; try { await loadReview(); } catch (e) { el('reviewError').textContent = e.message; } };
api('/demo/employees').then(rows => {
  for (const employee of rows) {
    const option = text('option', employee.employee_id + ' · ' + employee.name + ' · ' + employee.department); option.value = employee.employee_id; el('employee').append(option);
    if (employee.roles.some(role => ['manager','it_reviewer','security_reviewer'].includes(role))) el('reviewer').append(option.cloneNode(true));
  }
  setBusy(false);
}).catch(e => el('error').textContent = e.message);
