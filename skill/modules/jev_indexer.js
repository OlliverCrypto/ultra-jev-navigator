(() => {
  // Remove existing overlays
  const existingContainer = document.getElementById('__jev_overlay_container__');
  if (existingContainer) existingContainer.remove();

  const container = document.createElement('div');
  container.id = '__jev_overlay_container__';
  container.style.position = 'fixed';
  container.style.top = '0';
  container.style.left = '0';
  container.style.width = '100vw';
  container.style.height = '100vh';
  container.style.pointerEvents = 'none';
  container.style.zIndex = '2147483647';
  document.body.appendChild(container);

  const interactiveSelectors = [
    'button',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    'a[href]',
    '[role="button"]',
    '[role="link"]',
    '[role="checkbox"]',
    '[role="radio"]',
    '[role="combobox"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[contenteditable="true"]',
    '[tabindex]:not([tabindex="-1"])'
  ];

  const elements = Array.from(document.querySelectorAll(interactiveSelectors.join(',')));
  const indexed = [];
  let index = 1;

  for (const el of elements) {
    // Check visibility
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

    const rect = el.getBoundingClientRect();
    if (rect.width <= 2 || rect.height <= 2) continue;
    // Check if within viewport
    if (rect.bottom < 0 || rect.top > window.innerHeight || rect.right < 0 || rect.left > window.innerWidth) continue;

    // Attribute dynamic test id to element
    el.setAttribute('data-jev-id', index.toString());

    // Create visual badge overlay
    const badge = document.createElement('div');
    badge.innerText = `[${index}]`;
    badge.style.position = 'absolute';
    badge.style.left = `${Math.max(0, rect.left)}px`;
    badge.style.top = `${Math.max(0, rect.top - 18)}px`;
    badge.style.backgroundColor = '#f59e0b';
    badge.style.color = '#000000';
    badge.style.fontSize = '11px';
    badge.style.fontWeight = 'bold';
    badge.style.fontFamily = 'monospace';
    badge.style.padding = '1px 4px';
    badge.style.borderRadius = '3px';
    badge.style.boxShadow = '0 2px 4px rgba(0,0,0,0.4)';
    badge.style.border = '1px solid #d97706';
    badge.style.zIndex = '2147483647';
    container.appendChild(badge);

    // Get clean label with support for associated labels and IDs
    let associatedLabel = '';
    if (el.labels && el.labels.length > 0) {
      associatedLabel = el.labels[0].innerText?.trim();
    } else if (el.id) {
      const lbl = document.querySelector(`label[for="${el.id}"]`);
      if (lbl) associatedLabel = lbl.innerText?.trim();
    }

    let label = el.getAttribute('aria-label') || 
                associatedLabel ||
                el.getAttribute('placeholder') || 
                el.getAttribute('title') || 
                el.innerText?.trim() || 
                el.name ||
                el.id ||
                el.value || '';
    if (label.length > 50) label = label.substring(0, 47) + '...';

    const role = el.getAttribute('role') || el.tagName.toLowerCase();
    const type = el.getAttribute('type') || '';

    indexed.push({
      id: index,
      tag: el.tagName.toLowerCase(),
      role: role,
      type: type,
      label: label.replace(/\s+/g, ' '),
      value: el.value || '',
      checked: el.checked || false,
      rect: {
        x: Math.round(rect.x + rect.width / 2),
        y: Math.round(rect.y + rect.height / 2),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      }
    });

    index++;
  }

  window.__jev_elements__ = indexed;
  return indexed;
})();
