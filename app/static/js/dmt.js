// dmt.js - Data Migration Tool UI logic

function previewImport() {
  const form = document.getElementById('importForm');
  const formData = new FormData(form);
  fetch('/dmt/import', {
    method: 'POST',
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      document.getElementById('importPreview').innerHTML = data.preview_html || '<div class="alert alert-danger">Preview failed.</div>';
    });
}

function exportData(type) {
  window.location = `/dmt/export/${type}`;
}

// Optionally, fetch migration logs on page load
window.addEventListener('DOMContentLoaded', function() {
  fetch('/dmt/logs')
    .then(res => res.text())
    .then(html => {
      document.getElementById('migrationLogs').innerHTML = html;
    });
});
