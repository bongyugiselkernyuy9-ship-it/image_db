// Antigravity Document Management System - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // 1. Auto-dismiss alert notifications after 5 seconds
    const alerts = document.querySelectorAll('.alert-custom');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                alert.remove();
            }, 500);
        }, 5000);
    });

    // 2. Drag & Drop File Zone implementation
    const dropzone = document.querySelector('.file-dropzone');
    const fileInput = document.querySelector('.file-dropzone input[type="file"]');
    
    if (dropzone && fileInput) {
        // Trigger file open when clicking dropzone
        dropzone.addEventListener('click', () => {
            fileInput.click();
        });

        // Hover visual feedback
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.style.borderColor = 'var(--accent-secondary)';
                dropzone.style.background = 'rgba(6, 182, 212, 0.05)';
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.style.borderColor = 'var(--border-color)';
                dropzone.style.background = 'var(--bg-secondary)';
            }, false);
        });

        // Handle drop event
        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length) {
                fileInput.files = files;
                updateDropzoneText(files[0].name);
            }
        });

        // Handle normal file input change
        fileInput.addEventListener('change', (e) => {
            if (fileInput.files.length) {
                updateDropzoneText(fileInput.files[0].name);
            }
        });

        function updateDropzoneText(fileName) {
            const textElement = dropzone.querySelector('p');
            const iconElement = dropzone.querySelector('.file-dropzone-icon');
            if (textElement) {
                textElement.innerHTML = `<strong>Selected file:</strong><br>${fileName}`;
            }
            if (iconElement) {
                iconElement.className = 'file-dropzone-icon bi bi-file-earmark-check-fill';
                iconElement.style.color = 'var(--success)';
            }
        }
    }
});
