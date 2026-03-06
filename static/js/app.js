/**
 * Preact application entry point
 * Mounts the root <App> component
 */
import { render } from 'preact';
import { useEffect } from 'preact/hooks';
import { html } from './htm.js';
import {
    getState, setState, useStore,
    loadModels, loadSessions, loadConfigMeta, handlePageVisible, handlePageUnload,
    startStream, stopStream, resetView, toggleSidebar, discoverModels,
} from './state.js';
import { Header } from './components/Header.js';
import { Sidebar } from './components/Sidebar.js';
import { InputPanel } from './components/InputPanel.js';
import { OutputPanel } from './components/OutputPanel.js';
import { SettingsModal } from './components/SettingsModal.js';

function App() {
    const sidebarOpen = useStore(s => s.sidebarOpen);

    // Initialize theme on mount
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', getState().theme);
    }, []);

    // Load models, sessions, and config meta on mount
    useEffect(() => {
        loadModels();
        loadSessions();
        loadConfigMeta();
        discoverModels();
    }, []);

    // Refresh state when tab becomes visible (bfcache restore, tab switch back)
    useEffect(() => {
        function onVisible() {
            if (document.visibilityState === 'visible') handlePageVisible();
        }
        document.addEventListener('visibilitychange', onVisible);
        return () => document.removeEventListener('visibilitychange', onVisible);
    }, []);

    // Kill auto-kill + live sessions on page unload (tab close, navigation away)
    useEffect(() => {
        window.addEventListener('beforeunload', handlePageUnload);
        return () => window.removeEventListener('beforeunload', handlePageUnload);
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
                resetView();
                setState({ question: '' });
            }
            if (isMod && e.key === 'b') {
                e.preventDefault();
                toggleSidebar();
            }
        }

        document.addEventListener('keydown', onKeyDown);
        return () => document.removeEventListener('keydown', onKeyDown);
    }, []);

    return html`
        <div class="app-layout">
            <${Sidebar} />
            <div class="app-main">
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
            </div>
            <${SettingsModal} />
        </div>
    `;
}

render(html`<${App} />`, document.getElementById('app'));
