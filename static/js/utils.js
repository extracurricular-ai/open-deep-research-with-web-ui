/**
 * Utility functions for Open Deep Research UI
 * ES module — imported by components
 */

/**
 * Escape HTML entities to prevent XSS
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Render markdown text to sanitized HTML
 * Uses marked.js for parsing and DOMPurify for sanitization
 */
export function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked === 'undefined') {
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    marked.setOptions({
        breaks: true,
        gfm: true,
        highlight: function(code, lang) {
            if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) { /* fallback */ }
            }
            if (typeof hljs !== 'undefined') {
                try {
                    return hljs.highlightAuto(code).value;
                } catch (e) { /* fallback */ }
            }
            return escapeHtml(code);
        }
    });

    const html = marked.parse(text);

    if (typeof DOMPurify !== 'undefined') {
        return DOMPurify.sanitize(html, {
            // Strip inline styles (blocks position:absolute, z-index hacks, etc.)
            FORBID_ATTR: ['style'],
            // Strip layout-breaking and ad-related tags
            FORBID_TAGS: ['iframe', 'object', 'embed', 'form', 'input', 'button', 'section'],
            // Only allow safe content tags
            ALLOWED_TAGS: [
                'a', 'b', 'i', 'em', 'strong', 'p', 'br', 'hr', 'div', 'span',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'dl', 'dt', 'dd',
                'table', 'thead', 'tbody', 'tr', 'th', 'td',
                'pre', 'code', 'blockquote',
                'img', 'del', 'ins', 'sub', 'sup', 'mark',
            ],
            // Only allow safe attributes
            ALLOWED_ATTR: [
                'href', 'title', 'alt', 'src', 'class', 'id',
                'target', 'rel', 'width', 'height',
            ],
        });
    }
    return html;
}

/**
 * Format elapsed seconds into human-readable string
 */
export function formatElapsedTime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m < 60) return `${m}m ${s}s`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}h ${rm}m`;
}

/**
 * Copy text to clipboard and show feedback on button
 */
export function copyToClipboard(text, buttonEl) {
    navigator.clipboard.writeText(text).then(() => {
        const original = buttonEl.textContent;
        buttonEl.textContent = 'Copied!';
        buttonEl.style.opacity = '1';
        setTimeout(() => {
            buttonEl.textContent = original;
            buttonEl.style.opacity = '';
        }, 2000);
    }).catch(() => {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);

        const original = buttonEl.textContent;
        buttonEl.textContent = 'Copied!';
        setTimeout(() => { buttonEl.textContent = original; }, 2000);
    });
}

/**
 * Syntax-highlight JSON string using highlight.js
 */
export function highlightJson(jsonStr) {
    if (typeof hljs !== 'undefined') {
        try {
            return hljs.highlight(jsonStr, { language: 'json' }).value;
        } catch (e) { /* fallback */ }
    }
    return escapeHtml(jsonStr);
}
