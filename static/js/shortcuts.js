/**
 * Keyboard shortcuts for Open Deep Research UI
 */

document.addEventListener('keydown', (e) => {
    // Ctrl+Enter or Cmd+Enter — submit form
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn && !submitBtn.disabled) {
            document.getElementById('queryForm').dispatchEvent(new Event('submit'));
        }
    }

    // Escape — stop agent
    if (e.key === 'Escape') {
        const stopBtn = document.getElementById('stopBtn');
        if (stopBtn && stopBtn.style.display !== 'none') {
            stopBtn.click();
        }
    }

    // Ctrl+K — focus question input
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const questionInput = document.getElementById('question');
        if (questionInput) questionInput.focus();
    }

    // Ctrl+L — clear
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
        e.preventDefault();
        const clearBtn = document.getElementById('clearBtn');
        if (clearBtn) clearBtn.click();
    }
});
