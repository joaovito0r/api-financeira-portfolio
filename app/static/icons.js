/**
 * Icon Library — Lucide (MIT)
 * SVGs inline para uso em todas as páginas.
 * Uso: <span data-icon="chart"></span>  ou  Icons.chart({ size: 16 })
 *
 * Estilo: stroke=currentColor, stroke-width=1.75 (consistente com gold)
 */

const ICON_LIBRARY = {
  // Navegação
  chart:      '<path d="M3 3v18h18"/><path d="M7 16l4-4 4 4 5-5"/>',
  wallet:     '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2"/><path d="M3 7h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H3"/><circle cx="17" cy="13" r="1"/>',
  star:       '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.904l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/>',
  compare:    '<path d="M3 6h18"/><path d="M3 12h18"/><path d="M3 18h12"/><path d="M16 16l2 2 4-4"/>',
  report:     '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>',
  bell:       '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .75-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  user:       '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',

  // Indicadores
  trend:      '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  trendingUp: '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  coins:      '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="M16.71 13.88l.7.71-2.82 2.82"/>',
  factory:    '<path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M17 18h1"/><path d="M12 18h1"/><path d="M7 18h1"/>',

  // Ações
  search:     '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  plus:       '<path d="M5 12h14"/><path d="M12 5v14"/>',
  trash:      '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  x:          '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  check:      '<path d="M20 6 9 17l-5-5"/>',
  edit:       '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>',
  refresh:    '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
  menu:       '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
  arrowRight: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  download:   '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  filter:     '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',

  // Feedback
  warning:    '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
  info:       '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="16" y2="12"/><line x1="12" x2="12.01" y1="8" y2="8"/>',
  error:      '<circle cx="12" cy="12" r="10"/><line x1="15" x2="9" y1="9" y2="15"/><line x1="9" x2="15" y1="9" y2="15"/>',
  success:    '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',

  // Visualização
  eye:        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff:     '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 11 7 11 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 1 12s4 7 11 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="1" x2="23" y1="1" y2="23"/>',
  pie:        '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
  bar:        '<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>',
  spark:      '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
  help:       '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" x2="12.01" y1="17" y2="17"/>',

  // Setores
  droplets:   '<path d="M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z"/><path d="M12.56 14.69c1.46 0 2.64-1.22 2.64-2.7 0-.78-.38-1.51-1.13-2.13C13.33 9.24 12.77 8.5 12.56 7.7c-.21.8-.77 1.54-1.51 2.16-.75.62-1.13 1.35-1.13 2.13 0 1.48 1.18 2.7 2.64 2.7z"/><path d="M17 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S17.29 6.75 17 5.3c-.29 1.45-1.14 2.84-2.29 3.76S13 11.1 13 12.25c0 2.22 1.8 4.05 4 4.05z"/>',
  bank:       '<path d="M3 22h18"/><path d="M6 18v-6"/><path d="M10 18v-6"/><path d="M14 18v-6"/><path d="M18 18v-6"/><path d="M12 2 2 7l10 5 10-5L12 2z"/><path d="M2 12h20"/>',
  zap:        '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  package:    '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',

  // Outros
  external:   '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  copy:       '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  lock:       '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  logout:     '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
};

/**
 * Renderiza um ícone SVG.
 * @param {string} name - Nome do ícone em ICON_LIBRARY
 * @param {object} opts - { size, className, strokeWidth }
 * @returns {string} HTML do SVG
 */
function icon(name, opts = {}) {
  const inner = ICON_LIBRARY[name];
  if (!inner) {
    console.warn(`[icons] ícone desconhecido: ${name}`);
    return '';
  }
  const {
    size = 16,
    className = '',
    strokeWidth = 1.75,
    title = '',
  } = opts;
  const titleTag = title ? `<title>${escapeHtml(title)}</title>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" class="${className}" aria-hidden="true">${titleTag}${inner}</svg>`;
}

/**
 * Substitui todos os elementos <span data-icon="..."> por SVGs.
 * Use data-icon="chart" data-icon-size="18" data-icon-class="..."
 */
function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach(el => {
    const name = el.getAttribute('data-icon');
    const size = parseInt(el.getAttribute('data-icon-size') || '16', 10);
    const cls = el.getAttribute('data-icon-class') || '';
    if (ICON_LIBRARY[name]) {
      el.innerHTML = icon(name, { size, className: cls });
    }
  });
}

/**
 * Toast de feedback.
 * @param {string} message
 * @param {string} type - 'success' | 'error' | 'info'
 * @param {number} duration - ms
 */
function showToast(message, type = 'info', duration = 3500) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const iconName = type === 'success' ? 'success' : type === 'error' ? 'error' : 'info';
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.innerHTML = `${icon(iconName, { size: 18 })}<span>${escapeHtml(message)}</span>`;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 200ms, transform 200ms';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 220);
  }, duration);
}

/**
 * Skeleton genérico.
 * @param {string} type - 'line' | 'lines' | 'block' | 'bar' | 'row' | 'table-row' | 'card-row' | 'value'
 * @param {object} opts - { count, width }
 */
function skeleton(type = 'line', opts = {}) {
  if (type === 'lines') {
    const count = opts.count || 3;
    return `<div>${'<div class="skeleton skeleton-line"></div>'.repeat(count)}</div>`;
  }
  if (type === 'block') return `<div class="skeleton skeleton-block"></div>`;
  if (type === 'bar')    return `<div class="skeleton skeleton-bar"></div>`;

  if (type === 'row') {
    return `<div class="skeleton-row" style="${opts.width ? `width:${opts.width};` : ''}">
      <div class="skeleton" style="width:${opts.iconSize || '40%'};height:12px;"></div>
      <div class="skeleton skeleton-line" style="width:60%;"></div>
    </div>`;
  }

  if (type === 'value') {
    return `<div class="skeleton" style="height:22px;width:${opts.width || '60%'};"></div>`;
  }

  // 'line' default
  return `<div class="skeleton skeleton-line" style="${opts.width ? `width:${opts.width};` : ''}"></div>`;
}

/**
 * Skeleton de linha de tabela (com 6 colunas por padrão).
 */
function skeletonTableRow(cols = 6) {
  const cells = Array.from({ length: cols }, (_, i) => {
    const w = i === 0 ? '70%' : i === 1 ? '50%' : '60%';
    return `<td><div class="skeleton skeleton-line" style="width:${w};height:11px;"></div></td>`;
  }).join('');
  return `<tr>${cells}</tr>`;
}

/**
 * Skeleton de card de indicador (Dashboard).
 */
function skeletonCard() {
  return `<div class="card">
    <div class="skeleton" style="width:32px;height:32px;border-radius:8px;margin-bottom:8px;"></div>
    <div class="skeleton skeleton-line" style="width:60%;height:10px;"></div>
    <div class="skeleton" style="height:22px;width:70%;margin:6px 0 4px;"></div>
    <div class="skeleton skeleton-line" style="width:90%;height:9px;"></div>
    <div class="skeleton skeleton-line" style="width:40%;height:11px;margin-top:4px;"></div>
  </div>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Auto-hidratar quando DOM estiver pronto
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => hydrateIcons());
} else {
  hydrateIcons();
}
