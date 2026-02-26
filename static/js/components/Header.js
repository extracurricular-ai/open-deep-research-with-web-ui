import { html } from '../htm.js';
import { toggleTheme, toggleSidebar, useStore } from '../state.js';

export function Header() {
    const theme = useStore(s => s.theme);
    const sidebarOpen = useStore(s => s.sidebarOpen);

    return html`
        <header>
            <div class="header-inner">
                <div class="header-title">
                    ${!sidebarOpen && html`
                        <button
                            class="btn btn-ghost sidebar-hamburger"
                            onClick=${toggleSidebar}
                            aria-label="Toggle sidebar"
                        >\u2630</button>
                    `}
                    <h1>open deep research</h1>
                    <span class="header-tag">agent</span>
                </div>
                <button
                    class="theme-toggle"
                    onClick=${toggleTheme}
                    aria-label="Toggle theme"
                >
                    ${theme === 'dark' ? '\u2600' : '\u263E'}
                </button>
            </div>
        </header>
    `;
}
