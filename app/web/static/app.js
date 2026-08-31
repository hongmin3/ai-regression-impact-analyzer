function bindDropzones(root) {
  (root || document).querySelectorAll('.dropzone').forEach((zone) => {
    const input = document.getElementById(zone.dataset.for);
    if (!input || zone.dataset.bound) return;
    zone.dataset.bound = '1';
    const label = zone.dataset.placeholder || zone.textContent;
    const refresh = () => {
      if (!input.files.length) {
        zone.textContent = label;
      } else if (input.files.length === 1) {
        zone.textContent = input.files[0].name;
      } else {
        zone.textContent = `${input.files.length}개 파일 선택됨 (${Array.from(input.files).map((f) => f.name).join(', ')})`;
      }
    };
    zone.addEventListener('click', () => input.click());
    input.addEventListener('change', refresh);
    ['dragenter', 'dragover'].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
      })
    );
    ['dragleave', 'drop'].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
      })
    );
    zone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event('change'));
      }
    });
    refresh();
  });
}

function formatKst(iso) {
  try {
    const parts = new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).formatToParts(new Date(iso));
    const get = (type) => (parts.find((p) => p.type === type) || {}).value || '';
    return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')} KST`;
  } catch (e) {
    return iso;
  }
}

function applyKstTimestamps(root) {
  (root || document).querySelectorAll('[data-utc-time]').forEach((el) => {
    const iso = el.dataset.utcTime;
    if (iso) el.textContent = formatKst(iso);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  bindDropzones();
  applyKstTimestamps();
});
