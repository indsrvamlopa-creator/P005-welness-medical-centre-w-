// Admin list pages: tuck the filter column into a small "Filter" button with a dropdown.
(() => {
  const filter = document.getElementById('changelist-filter');
  const changelist = document.getElementById('changelist');
  if (!filter || !changelist || !document.body.classList.contains('cw-shell')) return;

  // A filter group is active when its selected choice is not the first ("All"/"Any date").
  const groups = filter.querySelectorAll('ul');
  const activeCount = [...groups].filter((list) => {
    const selected = list.querySelector('li.selected');
    return selected && selected !== list.querySelector('li');
  }).length;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'cw-filter-button';
  button.setAttribute('aria-controls', 'changelist-filter');
  button.setAttribute('aria-expanded', 'false');
  button.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16l-6.2 7.4V18l-3.6 2v-7.6z"/></svg>' +
    '<span>Filter</span>' +
    (activeCount ? `<b class="cw-filter-count" aria-label="${activeCount} active">${activeCount}</b>` : '');
  if (activeCount) button.classList.add('has-active');

  const anchor = document.createElement('div');
  anchor.className = 'cw-filter-anchor';
  anchor.append(button, filter);

  // Sit beside the search box, or start a toolbar row when the list has no search.
  const searchRow = document.querySelector('#changelist-search > div') || document.getElementById('changelist-search');
  if (searchRow) {
    searchRow.append(anchor);
  } else {
    const bar = document.createElement('div');
    bar.id = 'toolbar';
    bar.className = 'cw-filter-bar';
    bar.append(anchor);
    (changelist.querySelector('.changelist-form-container') || changelist).prepend(bar);
  }
  changelist.classList.add('cw-filter-popover');

  const setOpen = (open) => {
    filter.classList.toggle('is-open', open);
    button.setAttribute('aria-expanded', String(open));
    if (open) filter.querySelector('a')?.focus({ preventScroll: true });
  };
  button.addEventListener('click', () => setOpen(!filter.classList.contains('is-open')));
  document.addEventListener('click', (event) => {
    if (!anchor.contains(event.target)) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && filter.classList.contains('is-open')) {
      setOpen(false);
      button.focus();
    }
  });
})();

// Admin list pages: label each cell with its column name for the phone card layout.
(() => {
  const table = document.getElementById('result_list');
  if (!table) return;
  const labels = [...table.querySelectorAll('thead th')].map((th) =>
    (th.querySelector('.text') || th).textContent.trim(),
  );
  table.querySelectorAll('tbody tr').forEach((row) => {
    [...row.children].forEach((cell, i) => {
      if (labels[i]) cell.dataset.label = labels[i];
    });
  });
})();

// Admin list pages: if the table is still wider than its card, show rows as cards instead of scrolling.
(() => {
  const table = document.getElementById('result_list');
  const results = table && table.closest('.results');
  if (!results) return;
  // Cards are only a last resort on narrow screens; computers always get the table.
  const fit = () => {
    table.classList.remove('cw-cards');
    if (window.innerWidth < 1024 && results.scrollWidth > results.clientWidth + 1) table.classList.add('cw-cards');
  };
  fit();
  let timer;
  window.addEventListener('resize', () => {
    clearTimeout(timer);
    timer = setTimeout(fit, 120);
  });
})();
