import { html } from '../htm.js';
import { useStore } from '../state.js';
import { renderMarkdown, copyToClipboard } from '../utils.js';

export function AnswerBox() {
    const answer = useStore(s => s.finalAnswer);
    if (!answer) return null;

    function onCopy(e) {
        copyToClipboard(answer, e.currentTarget);
    }

    return html`
        <div class="answer-box">
            <div class="answer-box-header">
                <span class="answer-box-label">Final Answer</span>
                <button class="btn-copy" onClick=${onCopy}>Copy</button>
            </div>
            <div
                class="answer-box-content markdown-body"
                dangerouslySetInnerHTML=${{ __html: renderMarkdown(answer) }}
            />
        </div>
    `;
}
