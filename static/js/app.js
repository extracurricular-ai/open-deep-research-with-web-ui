/**
 * Preact application entry point
 * Mounts the root <App> component
 */
import { render } from 'preact';
import { useEffect } from 'preact/hooks';
import { html } from './htm.js';
import { getState, setState, loadModels, startStream, stopStream, resetState } from './state.js';
import { Header } from './components/Header.js';
import { InputPanel } from './components/InputPanel.js';
import { OutputPanel } from './components/OutputPanel.js';

function App() {
    // Initialize theme on mount
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', getState().theme);
    }, []);

    // Load models on mount
    useEffect(() => {
        loadModels();
    }, []);

    // Global keyboard shortcuts
    useEffect(() => {
        function onKeyDown(e) {
            const isMod = e.ctrlKey || e.metaKey;

            if (isMod && e.key === 'Enter') {
                e.preventDefault();
                startStream();
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                stopStream();
            }
            if (isMod && e.key === 'k') {
                e.preventDefault();
                const input = document.getElementById('question');
                if (input) input.focus();
            }
            if (isMod && e.key === 'l') {
                e.preventDefault();
                resetState();
                setState({ question: '' });
            }
        }

        document.addEventListener('keydown', onKeyDown);
        return () => document.removeEventListener('keydown', onKeyDown);
    }, []);

    return html`
        <div class="container">
            <${Header} />
            <div class="main-content">
                <${InputPanel} />
                <${OutputPanel} />
            </div>
            <footer>
                <p>Powered by smolagents and LiteLLM</p>
            </footer>
        </div>
    `;
}

render(html`<${App} />`, document.getElementById('app'));
