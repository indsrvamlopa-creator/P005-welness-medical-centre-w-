const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('.main-nav');

if (menuButton && navigation) {
  menuButton.addEventListener('click', () => {
    const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!isOpen));
    menuButton.setAttribute('aria-label', isOpen ? 'Open menu' : 'Close menu');
    navigation.classList.toggle('is-open', !isOpen);
  });

  navigation.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      menuButton.setAttribute('aria-expanded', 'false');
      menuButton.setAttribute('aria-label', 'Open menu');
      navigation.classList.remove('is-open');
    });
  });
}

const bmiForm = document.getElementById('bmi-form');

if (bmiForm) {
  const result = document.getElementById('bmi-result');
  const report = document.getElementById('bmi-report');
  const byId = (id) => document.getElementById(id);
  const DISCLAIMER = 'BMI is a general guide for adults. It does not account for muscle, age, pregnancy or body shape, and it is not medical advice.';
  // Upper limits (exclusive) for each adult BMI band.
  const bands = [
    { key: 'under', limit: 18.5, label: 'Underweight',
      summary: 'Your BMI is below the healthy range. A balanced nutrition plan can help you build healthy weight, strength and energy.' },
    { key: 'healthy', limit: 25, label: 'Healthy weight',
      summary: 'Your BMI is in the healthy range. Keep it up with balanced meals, good hydration and regular activity.' },
    { key: 'over', limit: 30, label: 'Overweight',
      summary: 'Your BMI is a little above the healthy range. Small, steady changes to meals and activity can make a real difference.' },
    { key: 'obese', limit: Infinity, label: 'Obese',
      summary: 'Your BMI is above the healthy range. Personal support can help you start with simple, sustainable steps. Please also check with your doctor.' },
  ];
  const HEALTHY_MIN = 18.5;
  const HEALTHY_MAX = 24.9;
  // The scale bar shows BMI 15 to 40.
  const SCALE_MIN = 15;
  const SCALE_MAX = 40;
  const kg = (value) => `${value.toFixed(1)} kg`;

  bmiForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const heightCm = Number(byId('bmi-height').value);
    const weightKg = Number(byId('bmi-weight').value);

    if (!(heightCm >= 50 && heightCm <= 250 && weightKg >= 10 && weightKg <= 350)) {
      report.hidden = true;
      result.textContent = 'Please enter a height between 50 and 250 cm and a weight between 10 and 350 kg.';
      return;
    }

    const heightM2 = (heightCm / 100) ** 2;
    // Classify the rounded value so the number shown always matches its label.
    const bmi = Math.round((weightKg / heightM2) * 10) / 10;
    const band = bands.find(({ limit }) => bmi < limit);
    const minWeight = HEALTHY_MIN * heightM2;
    const maxWeight = HEALTHY_MAX * heightM2;

    byId('bmi-value').textContent = bmi.toFixed(1);
    const badge = byId('bmi-category');
    badge.textContent = band.label;
    badge.dataset.band = band.key;
    byId('bmi-summary').textContent = band.summary;
    byId('bmi-healthy-range').textContent = `${kg(minWeight)} – ${kg(maxWeight)}`;
    byId('bmi-weight-out').textContent = `${kg(weightKg)} at ${heightCm} cm`;
    if (weightKg < minWeight) {
      byId('bmi-gap').textContent = `Gain about ${kg(minWeight - weightKg)}`;
    } else if (weightKg > maxWeight) {
      byId('bmi-gap').textContent = `Lose about ${kg(weightKg - maxWeight)}`;
    } else {
      byId('bmi-gap').textContent = 'You are already in the healthy range';
    }
    report.querySelectorAll('.bmi-ranges li').forEach((item) => {
      item.classList.toggle('is-active', item.dataset.band === band.key);
    });
    const position = Math.min(Math.max((bmi - SCALE_MIN) / (SCALE_MAX - SCALE_MIN), 0), 1) * 100;

    report.hidden = false;
    report.classList.remove('is-shown');
    void report.offsetWidth;  // Restart the fade-in on every calculation.
    report.classList.add('is-shown');
    // Let the marker slide from the left edge to the visitor's position.
    const marker = byId('bmi-marker');
    marker.style.left = '0%';
    requestAnimationFrame(() => requestAnimationFrame(() => { marker.style.left = `${position}%`; }));
    result.textContent = DISCLAIMER;
  });
}

document.querySelectorAll('.event-dialog').forEach((dialog) => {
  const open = () => {
    if (typeof dialog.showModal !== 'function') {
      dialog.setAttribute('open', '');  // Very old browsers: show it inline instead.
      return;
    }
    dialog.showModal();
    const firstInput = dialog.querySelector('.field-error')
      ? dialog.querySelector('.field-error').closest('.field-wrap')?.querySelector('input, select, textarea')
      : dialog.querySelector('input:not([type="hidden"]), select, textarea');
    firstInput?.focus();
  };

  document.querySelectorAll(`[data-dialog="${dialog.id}"]`).forEach((trigger) => {
    trigger.addEventListener('click', open);
  });
  dialog.querySelector('.event-dialog-close')?.addEventListener('click', () => dialog.close());
  // Clicking the dimmed backdrop closes the popup; Esc is handled by the browser.
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });

  // Re-open after a submission with errors, or when arriving via ?event=<id>.
  if (dialog.hasAttribute('data-open-on-load')) open();
});

// Fade cards in one after another as they scroll into view.
const revealItems = document.querySelectorAll('[data-reveal]');
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (revealItems.length && 'IntersectionObserver' in window && !prefersReducedMotion) {
  document.documentElement.classList.add('reveal-ready');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });
  revealItems.forEach((item) => observer.observe(item));
}

// Hero background video: pause/play button, and no motion for visitors who ask for less.
const heroVideo = document.getElementById('hero-video');
const heroToggle = document.getElementById('hero-video-toggle');

if (heroVideo && heroToggle) {
  const showState = () => {
    const paused = heroVideo.paused;
    heroToggle.setAttribute('aria-label', paused ? 'Play background video' : 'Pause background video');
    heroToggle.firstElementChild.className = paused ? 'icon-play' : 'icon-pause';
  };
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    heroVideo.removeAttribute('autoplay');
    heroVideo.pause();
  }
  heroToggle.addEventListener('click', () => {
    if (heroVideo.paused) {
      heroVideo.play().catch(() => {});
    } else {
      heroVideo.pause();
    }
  });
  heroVideo.addEventListener('play', showState);
  heroVideo.addEventListener('pause', showState);
  showState();
}

// Reviews: show the first four, reveal the rest on request.
const reviewsMore = document.getElementById('reviews-more');

if (reviewsMore) {
  const extras = document.querySelectorAll('.review-extra');
  reviewsMore.addEventListener('click', () => {
    const expand = reviewsMore.getAttribute('aria-expanded') !== 'true';
    extras.forEach((card) => { card.hidden = !expand; });
    reviewsMore.setAttribute('aria-expanded', String(expand));
    reviewsMore.firstChild.textContent = `${expand ? reviewsMore.dataset.lessLabel : reviewsMore.dataset.moreLabel} `;
    if (expand) {
      extras[0]?.querySelector('button, a')?.focus({ preventScroll: true });
    } else {
      document.getElementById('reviews')?.scrollIntoView({ block: 'start' });
    }
  });
}

// Services slider: arrows, progress line, and hiding controls when everything fits.
document.querySelectorAll('[data-slider]').forEach((slider) => {
  const track = slider.querySelector('[data-slider-track]');
  const prev = slider.querySelector('[data-slider-prev]');
  const next = slider.querySelector('[data-slider-next]');
  const progress = slider.querySelector('[data-slider-progress]');
  const bar = progress?.firstElementChild;
  if (!track || !prev || !next) return;

  const step = () => {
    const card = track.firstElementChild;
    const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    return card ? card.getBoundingClientRect().width + gap : track.clientWidth;
  };

  const update = () => {
    const maxScroll = track.scrollWidth - track.clientWidth;
    const scrollable = maxScroll > 2;
    slider.classList.toggle('is-static', !scrollable);
    prev.hidden = next.hidden = !scrollable;
    if (progress) progress.hidden = !scrollable;
    if (!scrollable) return;
    prev.disabled = track.scrollLeft <= 2;
    next.disabled = track.scrollLeft >= maxScroll - 2;
    if (bar) {
      const visible = track.clientWidth / track.scrollWidth;
      const position = track.scrollLeft / maxScroll;
      bar.style.setProperty('--progress-size', `${visible * 100}%`);
      bar.style.setProperty('--progress-x', `${position * ((1 - visible) / visible) * 100}%`);
    }
  };

  prev.addEventListener('click', () => track.scrollBy({ left: -step(), behavior: 'smooth' }));
  next.addEventListener('click', () => track.scrollBy({ left: step(), behavior: 'smooth' }));
  track.addEventListener('scroll', update, { passive: true });
  track.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight') { event.preventDefault(); next.click(); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); prev.click(); }
  });
  window.addEventListener('resize', update);
  update();
});

// About section photo slideshow: cross-fades every few seconds, pauses on hover.
document.querySelectorAll('[data-about-slider]').forEach((slider) => {
  const slides = [...slider.querySelectorAll('.about-slide')];
  const dots = [...slider.querySelectorAll('.about-dot')];
  if (slides.length < 2) return;

  const INTERVAL = 5000;
  slider.style.setProperty('--about-interval', `${INTERVAL}ms`);
  const autoplay = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let current = 0;
  let timer = null;

  // Later slides are lazy; load them once the first is showing so fades never flash empty.
  slides.forEach((slide) => slide.setAttribute('loading', 'eager'));

  const show = (index) => {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      slide.classList.toggle('is-active', i === current);
      slide.toggleAttribute('aria-hidden', i !== current);
    });
    dots.forEach((dot, i) => {
      dot.classList.toggle('is-active', i === current);
      if (i === current) dot.setAttribute('aria-current', 'true');
      else dot.removeAttribute('aria-current');
    });
  };

  const stop = () => {
    clearInterval(timer);
    timer = null;
    slider.classList.remove('is-playing');
  };
  const start = () => {
    if (!autoplay || timer) return;
    // Restart the active dot's progress bar in step with the timer.
    slider.classList.remove('is-playing');
    void slider.offsetWidth;
    slider.classList.add('is-playing');
    timer = setInterval(() => show(current + 1), INTERVAL);
  };

  dots.forEach((dot, i) => dot.addEventListener('click', () => {
    stop();
    show(i);
    if (!slider.matches(':hover')) start();
  }));
  slider.addEventListener('mouseenter', stop);
  slider.addEventListener('mouseleave', start);
  slider.addEventListener('focusin', stop);
  slider.addEventListener('focusout', start);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));

  // Only run while the photo is on screen.
  new IntersectionObserver(([entry]) => (entry.isIntersecting ? start() : stop())).observe(slider);
});

// "Book this" on a service card: pre-select that service in the booking popup.
const bookDialog = document.getElementById('book-dialog');
if (bookDialog) {
  const serviceSelect = bookDialog.querySelector('select[name="book-service"]');
  const heading = bookDialog.querySelector('[data-book-heading]');
  const updateHeading = () => {
    const option = serviceSelect?.selectedOptions[0];
    heading.textContent = option && option.value ? option.textContent : 'Book your session';
  };
  document.querySelectorAll('[data-book-service]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      if (serviceSelect) serviceSelect.value = link.dataset.bookService;
      updateHeading();
    });
  });
  serviceSelect?.addEventListener('change', updateHeading);
}

// Email is required only when "Email" is the preferred contact method.
document.querySelectorAll('form').forEach((form) => {
  const method = form.querySelector('select[name$="preferred_contact_method"]');
  const email = form.querySelector('input[name$="email"]');
  if (!method || !email) return;
  const optionalTag = form.querySelector(`label[for="${email.id}"] .optional-label`);
  const placeholder = email.getAttribute('placeholder') || '';
  const sync = () => {
    const needed = email.hasAttribute('data-always-required') || method.value === 'email';
    email.required = needed;
    if (optionalTag) optionalTag.hidden = needed;
    email.placeholder = needed ? placeholder.replace(' (optional)', '') : placeholder;
  };
  method.addEventListener('change', sync);
  sync();
});

// Form success / error messages close themselves after 3 seconds.
document.querySelectorAll('.form-messages .message').forEach((message) => {
  const close = () => {
    message.classList.add('is-leaving');
    setTimeout(() => {
      const box = message.closest('.form-messages');
      message.remove();
      if (box && !box.querySelector('.message')) box.remove();
    }, 400);
  };
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'message-close';
  button.setAttribute('aria-label', 'Close message');
  button.textContent = '×';
  button.addEventListener('click', close);
  message.append(button);
  setTimeout(close, 3000);
});
