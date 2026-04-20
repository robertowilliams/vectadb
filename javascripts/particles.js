/* VectaDB ambient orb particles — matches vectadb.base44.app */
(function () {
  // Only run in dark (slate) scheme
  function isDark() {
    return document.body.getAttribute('data-md-color-scheme') === 'slate';
  }

  // Orb definitions: top%, left%, size(px), color, blur(px), duration(s), delay(s)
  var orbs = [
    { top: '8%',  left: '10%', w: 420, h: 420, color: 'rgba(0,212,255,0.10)',  blur: 120, dur: 7,  delay: 0   },
    { top: '60%', left: '70%', w: 480, h: 480, color: 'rgba(0,212,255,0.08)',  blur: 140, dur: 9,  delay: 1.5 },
    { top: '30%', left: '80%', w: 320, h: 320, color: 'rgba(220,20,60,0.10)',  blur: 110, dur: 8,  delay: 0.5 },
    { top: '70%', left: '5%',  w: 360, h: 360, color: 'rgba(220,20,60,0.07)',  blur: 130, dur: 10, delay: 2   },
    { top: '45%', left: '45%', w: 500, h: 500, color: 'rgba(0,212,255,0.05)',  blur: 160, dur: 12, delay: 1   },
    { top: '85%', left: '55%', w: 280, h: 280, color: 'rgba(255,20,147,0.06)', blur: 100, dur: 11, delay: 3   },
    { top: '15%', left: '55%', w: 240, h: 240, color: 'rgba(0,212,255,0.07)',  blur: 90,  dur: 8,  delay: 2.5 },
  ];

  var container;

  function createOrbs() {
    container = document.createElement('div');
    container.id = 'vectadb-particles';
    container.style.cssText = [
      'position:fixed',
      'top:0', 'left:0',
      'width:100%', 'height:100%',
      'pointer-events:none',
      'z-index:0',
      'overflow:hidden',
    ].join(';');

    orbs.forEach(function (o, i) {
      var el = document.createElement('div');
      el.style.cssText = [
        'position:absolute',
        'top:'  + o.top,
        'left:' + o.left,
        'width:'  + o.w + 'px',
        'height:' + o.h + 'px',
        'background:' + o.color,
        'border-radius:50%',
        'filter:blur(' + o.blur + 'px)',
        'animation:vdb-pulse ' + o.dur + 's ease-in-out ' + o.delay + 's infinite',
        'will-change:opacity,transform',
      ].join(';');
      container.appendChild(el);
    });

    document.body.insertBefore(container, document.body.firstChild);
  }

  function removeOrbs() {
    var el = document.getElementById('vectadb-particles');
    if (el) el.remove();
  }

  function sync() {
    removeOrbs();
    if (isDark()) createOrbs();
  }

  // Inject keyframes once
  var style = document.createElement('style');
  style.textContent = [
    '@keyframes vdb-pulse {',
    '  0%,100% { opacity:1; transform:scale(1); }',
    '  50%      { opacity:0.45; transform:scale(1.08); }',
    '}',
  ].join('');
  document.head.appendChild(style);

  // Run on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', sync);
  } else {
    sync();
  }

  // Re-run whenever the user toggles light/dark
  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      if (m.attributeName === 'data-md-color-scheme') sync();
    });
  });
  observer.observe(document.body, { attributes: true });

  // Re-run on MkDocs instant navigation (page changes)
  document.addEventListener('DOMContentSwitch', sync);
})();
