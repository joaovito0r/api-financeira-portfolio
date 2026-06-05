/**
 * API Financeira - Cliente JavaScript
 *
 * Funções compartilhadas para consumir a API do backend.
 * Usa fetch() nativo, sem dependências externas.
 *
 * Depende de: icons.js (deve ser carregado ANTES deste arquivo)
 */

const API_BASE = '';

async function apiGet(path) {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `Erro ${resp.status}`);
  }
  return resp.json();
}

async function apiPost(path, body) {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `Erro ${resp.status}`);
  }
  return resp.json();
}

async function apiPut(path, body) {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `Erro ${resp.status}`);
  }
  return resp.json();
}

async function apiDelete(path) {
  const resp = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `Erro ${resp.status}`);
  }
  return resp.json();
}

function formatMoney(value) {
  if (value == null) return '-';
  return `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value) {
  if (value == null) return '-';
  const signal = value >= 0 ? '+' : '';
  return `${signal}${(value * 100).toFixed(2)}%`;
}

function formatChange(value) {
  if (value == null) return '-';
  const signal = value >= 0 ? '▲' : '▼';
  const cls = value >= 0 ? 'up' : 'down';
  return `<span class="${cls}">${signal} ${Math.abs(value).toFixed(2)}%</span>`;
}

function renderError(containerId, message) {
  const el = document.getElementById(containerId);
  if (el) {
    el.innerHTML = `<div class="loading-state">${icon('error', { size: 16 })}<span>${escapeHtml(message)}</span></div>`;
  }
}

function renderLoading(containerId, message = 'Carregando…') {
  const el = document.getElementById(containerId);
  if (el) {
    el.innerHTML = `<div class="loading-state"><span class="spinner"></span><span>${escapeHtml(message)}</span></div>`;
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Sidebar (hamburger mobile) ──────────────────────────────

function initSidebar() {
  const toggle = document.querySelector('.menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (!toggle || !sidebar) return;

  // Criar backdrop sob demanda
  let backdrop = document.querySelector('.sidebar-backdrop');
  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.className = 'sidebar-backdrop';
    document.body.appendChild(backdrop);
  }

  const close = () => {
    sidebar.classList.remove('open');
    backdrop.classList.remove('show');
    document.body.style.overflow = '';
  };
  const open = () => {
    sidebar.classList.add('open');
    backdrop.classList.add('show');
    document.body.style.overflow = 'hidden';
  };

  toggle.addEventListener('click', () => {
    if (sidebar.classList.contains('open')) close();
    else open();
  });
  backdrop.addEventListener('click', close);

  // Fechar com ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) close();
  });

  // Fechar ao navegar (em mobile)
  sidebar.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      if (window.matchMedia('(max-width: 640px)').matches) close();
    });
  });
}

// ── Modal de Confirmação (reutilizável) ─────────────────────

let _modalState = null;

function _buildModalContainer() {
  if (document.getElementById('hermes-confirm-overlay')) return;
  const div = document.createElement('div');
  div.innerHTML = `
<div class="modal-overlay" id="hermes-confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="hermes-modal-title">
  <div class="modal">
    <h2 id="hermes-modal-title"></h2>
    <div class="sub" id="hermes-modal-msg"></div>
    <div id="hermes-modal-body"></div>
    <div class="modal-actions" id="hermes-modal-actions"></div>
  </div>
</div>`;
  document.body.appendChild(div);
  const overlay = document.getElementById('hermes-confirm-overlay');

  // Fechar com ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _modalState && _modalState.type === 'confirm') {
      _closeModal();
    }
  });

  // Fechar clicando fora
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay && _modalState && _modalState.type === 'confirm') {
      _closeModal();
    }
  });
}

function _openModal() {
  const overlay = document.getElementById('hermes-confirm-overlay');
  overlay.classList.remove('closing');
  overlay.classList.add('show');
  document.body.style.overflow = 'hidden';

  // Prender foco dentro do modal
  const firstFocus = overlay.querySelector('button, input, [tabindex]');
  if (firstFocus) setTimeout(() => firstFocus.focus(), 50);
}

function _closeModal() {
  const overlay = document.getElementById('hermes-confirm-overlay');
  if (!overlay) return;
  overlay.classList.add('closing');
  setTimeout(() => {
    overlay.classList.remove('show', 'closing');
    document.body.style.overflow = '';
  }, 200);
}

function showConfirm(msg, btnText = 'Confirmar', opts = {}) {
  _buildModalContainer();
  const titleEl = document.getElementById('hermes-modal-title');
  const msgEl   = document.getElementById('hermes-modal-msg');
  const bodyEl  = document.getElementById('hermes-modal-body');
  const actEl   = document.getElementById('hermes-modal-actions');

  titleEl.innerHTML = `${icon('warning', { size: 18 })} Confirmação`;
  msgEl.textContent = msg;
  bodyEl.innerHTML = '';
  actEl.innerHTML = '';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn btn-outline';
  cancelBtn.textContent = 'Cancelar';
  cancelBtn.onclick = () => { _modalState = null; _closeModal(); };

  const confirmBtn = document.createElement('button');
  confirmBtn.className = `btn ${opts.danger ? 'btn-danger' : 'btn-primary'}`;
  confirmBtn.textContent = btnText;
  confirmBtn.onclick = () => {
    const cb = _modalState?.cb;
    _modalState = null;
    _closeModal();
    if (cb) cb();
  };

  actEl.appendChild(cancelBtn);
  actEl.appendChild(confirmBtn);
  _modalState = { type: 'confirm' };
  _openModal();
  return new Promise((resolve) => { _modalState.cb = resolve; });
}

function showPrompt(title, placeholder = '', defaultValue = '') {
  _buildModalContainer();
  const titleEl = document.getElementById('hermes-modal-title');
  const msgEl   = document.getElementById('hermes-modal-msg');
  const bodyEl  = document.getElementById('hermes-modal-body');
  const actEl   = document.getElementById('hermes-modal-actions');

  titleEl.innerHTML = title;
  msgEl.innerHTML = '&nbsp;';
  bodyEl.innerHTML = `<input id="hermes-prompt-input" value="${escapeHtml(defaultValue)}" placeholder="${escapeHtml(placeholder)}" autofocus>`;
  actEl.innerHTML = '';

  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn btn-outline';
  cancelBtn.textContent = 'Cancelar';
  cancelBtn.onclick = () => { _modalState = null; _closeModal(); };

  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'btn btn-primary';
  confirmBtn.textContent = 'OK';
  confirmBtn.onclick = () => {
    const val = document.getElementById('hermes-prompt-input')?.value || '';
    const cb = _modalState?.cb;
    _modalState = null;
    _closeModal();
    if (cb) cb(val);
  };

  actEl.appendChild(cancelBtn);
  actEl.appendChild(confirmBtn);
  _modalState = { type: 'prompt' };

  // Submeter com Enter
  setTimeout(() => {
    const input = document.getElementById('hermes-prompt-input');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') confirmBtn.click();
      });
      input.focus();
      input.select();
    }
  }, 100);

  _openModal();
  return new Promise((resolve) => { _modalState.cb = resolve; });
}

function showAlert(msg, title = 'Atenção') {
  _buildModalContainer();
  const titleEl = document.getElementById('hermes-modal-title');
  const msgEl   = document.getElementById('hermes-modal-msg');
  const bodyEl  = document.getElementById('hermes-modal-body');
  const actEl   = document.getElementById('hermes-modal-actions');

  titleEl.innerHTML = `${icon('info', { size: 18 })} ${escapeHtml(title)}`;
  msgEl.textContent = msg;
  bodyEl.innerHTML = '';
  actEl.innerHTML = '';

  const okBtn = document.createElement('button');
  okBtn.className = 'btn btn-primary';
  okBtn.textContent = 'OK';
  okBtn.onclick = () => { _modalState = null; _closeModal(); };
  actEl.appendChild(okBtn);

  _modalState = { type: 'alert' };
  _openModal();
}

// Inicializar sidebar ao carregar
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSidebar);
} else {
  initSidebar();
}
