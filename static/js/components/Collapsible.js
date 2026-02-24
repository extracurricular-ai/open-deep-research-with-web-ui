import { useState, useRef, useEffect } from 'preact/hooks';
import { html } from '../htm.js';
import { renderMarkdown, copyToClipboard } from '../utils.js';

export function Collapsible({ title, content, type, expanded = false, isMarkdown = false }) {
    const [isOpen, setOpen] = useState(expanded);
    const contentRef = useRef(null);

    useEffect(() => {
        if (contentRef.current) {
            if (isOpen) {
                contentRef.current.style.maxHeight = contentRef.current.scrollHeight + 'px';
            } else {
                contentRef.current.style.maxHeight = '0';
            }
        }
    }, [isOpen]);

    // Watch for content changes when open (e.g., images loading)
    useEffect(() => {
        if (!isOpen || !contentRef.current) return;
        if (typeof ResizeObserver === 'undefined') return;

        const observer = new ResizeObserver(() => {
            if (contentRef.current && isOpen) {
                contentRef.current.style.maxHeight = contentRef.current.scrollHeight + 'px';
            }
        });
        observer.observe(contentRef.current);
        return () => observer.disconnect();
    }, [isOpen]);

    function onToggle() {
        setOpen(!isOpen);
    }

    function onCopy(e) {
        e.stopPropagation();
        copyToClipboard(content || '', e.currentTarget);
    }

    return html`
        <div class="collapsible ${type} ${isOpen ? 'open' : ''}">
            <div class="collapsible-header" onClick=${onToggle}>
                <span class="collapsible-toggle">\u25B6</span>
                <span class="collapsible-title">${title}</span>
                <button class="btn-copy" onClick=${onCopy}>Copy</button>
            </div>
            <div
                class="collapsible-content ${isOpen ? 'open' : ''}"
                ref=${contentRef}
            >
                ${isMarkdown && content
                    ? html`<div class="markdown-body" dangerouslySetInnerHTML=${{ __html: renderMarkdown(content) }} />`
                    : html`<pre>${content || ''}</pre>`
                }
            </div>
        </div>
    `;
}
