import { html } from '../htm.js';
import { highlightJson, copyToClipboard } from '../utils.js';
import { Collapsible } from './Collapsible.js';

const BROWSER_NAV_TOOLS = new Set([
    'find_on_page_ctrl_f', 'find_next', 'page_up', 'page_down'
]);

function extractPageUrl(text) {
    if (!text) return null;
    const m = text.match(/^Address:\s*(https?:\/\/\S+)/m);
    return m ? m[1] : null;
}

export function ToolCall({ toolName, args, result }) {
    const jsonStr = typeof args === 'string'
        ? args
        : args != null ? JSON.stringify(args, null, 2) : null;

    const pageUrl = BROWSER_NAV_TOOLS.has(toolName) && result
        ? extractPageUrl(result)
        : null;

    function onCopy(e) {
        if (jsonStr) copyToClipboard(jsonStr, e.currentTarget);
    }

    return html`
        <div class="tool-call">
            <div class="tool-call-header">
                <span class="tool-name">${toolName || 'Unknown tool'}</span>
                ${jsonStr && html`
                    <button class="btn-copy" onClick=${onCopy}>Copy</button>
                `}
            </div>
            ${pageUrl && html`
                <div class="tool-page-url">${pageUrl}</div>
            `}
            ${jsonStr && html`
                <div class="tool-args" dangerouslySetInnerHTML=${{ __html: highlightJson(jsonStr) }} />
            `}
            ${result && html`
                <${Collapsible}
                    title="Result"
                    content=${result}
                    type="observation"
                    isMarkdown=${true}
                />
            `}
        </div>
    `;
}
