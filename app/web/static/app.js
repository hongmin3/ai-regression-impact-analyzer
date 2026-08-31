function bindDropzones(root) {
  (root || document).querySelectorAll('.dropzone').forEach((zone) => {
    const input = document.getElementById(zone.dataset.for);
    if (!input || zone.dataset.bound) return;
    zone.dataset.bound = '1';
    const label = zone.dataset.placeholder || zone.textContent;
    const refresh = () => {
      zone.textContent = input.files[0] ? input.files[0].name : label;
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

document.addEventListener('DOMContentLoaded', () => bindDropzones());
