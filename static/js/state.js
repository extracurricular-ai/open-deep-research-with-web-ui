/**
 * Application state — simple pub/sub store
 * Works reliably with CDN-loaded Preact (no signals dependency issues)
 *
 * Usage in components:
 *   const state = useStore();           // subscribes to all changes
 *   const models = useStore(s => s.models); // subscribes, returns models
 */
import { useState, useEffect, useRef } from 'preact/hooks';

// ===== Store =====
const state = {
    events: [],
    status: { message: '', type: '' },
    sessionId: null,
    isRunning: false,
    isStopped: false,
    theme: localStorage.getItem('odr-theme') || 'dark',
    activeFilter: 'all',
    historyOpen: false,
    models: [],
    selectedModel: '',
    question: '',
    finalAnswer: null,
    totalStartTime: null,
    runMode: localStorage.getItem('odr-run-mode') || 'background',

    // Sidebar session management
    sessions: [],
    sessionsLoading: false,
    activeSessionId: null,
    viewingHistory: false,
    viewingLiveSession: false,
    sidebarOpen: true,

    // Settings
    settingsOpen: false,
    enableConfigUI: false,
};

const listeners = new Set();

function notify() {
    listeners.forEach(fn => fn());
}

/**
 * Update state and notify subscribers
 */
export function setState(partial) {
    Object.assign(state, partial);
    notify();
}

/**
 * Get current state snapshot (read-only use outside components)
 */
export function getState() {
    return state;
}

/**
 * Hook: subscribe a component to store changes.
 * Optional selector for performance (only re-renders if selected value changes).
 */
export function useStore(selector) {
    const [, forceUpdate] = useState(0);
    const selectorRef = useRef(selector);
    const prevRef = useRef(selector ? selector(state) : undefined);
    selectorRef.current = selector;

    useEffect(() => {
        function onChange() {
            if (selectorRef.current) {
                const next = selectorRef.current(state);
                if (next !== prevRef.current) {
                    prevRef.current = next;
                    forceUpdate(n => n + 1);
                }
            } else {
                forceUpdate(n => n + 1);
            }
        }
        listeners.add(onChange);
        return () => listeners.delete(onChange);
    }, []);

    return selector ? selector(state) : state;
}

// ===== Computed Step Tree =====
// Cached — recomputed only when events array changes
let cachedEvents = null;
let cachedTree = [];

export function getStepTree() {
    if (state.events !== cachedEvents) {
        cachedEvents = state.events;
        cachedTree = buildStepTree(state.events);
    }
    return cachedTree;
}

/**
 * Build a nested tree from flat SSE events.
 */
function buildStepTree(eventList) {
    const tree = [];
    let pendingNode = null;
    let currentAgentName = null;

    for (let i = 0; i < eventList.length; i++) {
        const evt = eventList[i];

        switch (evt.type) {
            case 'code_running': {
                const code = evt.code || '';
                const agentMatch = code.match(/(\w+_agent)\s*\(/);

                if (agentMatch) {
                    pendingNode = {
                        type: 'pending',
                        label: `Calling ${agentMatch[1]}`,
                        agentCallName: agentMatch[1],
                        children: [],
                        subAgents: {},
                        timestamp: Date.now(),
                    };
                    tree.push(pendingNode);
                    currentAgentName = null;
                }
                break;
            }

            case 'action_step': {
                const agentName = evt.agent_name || null;
                const isCodeAgent = !!evt.code_action;
                const callsSubAgent = isCodeAgent &&
                    /\w+_agent\s*\(/.test(evt.code_action || '');

                if (pendingNode && !agentName && callsSubAgent) {
                    pendingNode.type = 'step';
                    pendingNode.data = evt;
                    pendingNode.label = null;
                    pendingNode = null;
                    currentAgentName = null;
                } else if (pendingNode && agentName) {
                    if (!pendingNode.subAgents[agentName]) {
                        pendingNode.subAgents[agentName] = { events: [] };
                    }
                    pendingNode.subAgents[agentName].events.push({
                        type: 'step',
                        data: evt,
                        children: [],
                        subAgents: {},
                    });
                    currentAgentName = agentName;
                } else {
                    const node = {
                        type: 'step',
                        data: evt,
                        children: [],
                        subAgents: {},
                    };
                    tree.push(node);
                    currentAgentName = agentName;
                }
                break;
            }

            case 'planning_step': {
                const agentName = evt.agent_name || null;
                const node = { type: 'plan', data: evt };

                if (pendingNode && agentName) {
                    if (!pendingNode.subAgents[agentName]) {
                        pendingNode.subAgents[agentName] = { events: [] };
                    }
                    pendingNode.subAgents[agentName].events.push(node);
                    currentAgentName = agentName;
                } else {
                    tree.push(node);
                }
                break;
            }

            case 'final_answer': {
                const agentName = evt.agent_name || null;
                const node = { type: 'final_answer', data: evt };

                if (pendingNode && agentName) {
                    if (!pendingNode.subAgents[agentName]) {
                        pendingNode.subAgents[agentName] = { events: [] };
                    }
                    pendingNode.subAgents[agentName].events.push(node);
                    currentAgentName = null;
                } else {
                    tree.push(node);
                }
                break;
            }

            case 'info':
            case 'error':
            case 'message':
            default: {
                const node = { type: evt.type || 'message', data: evt };
                if (pendingNode && currentAgentName) {
                    if (!pendingNode.subAgents[currentAgentName]) {
                        pendingNode.subAgents[currentAgentName] = { events: [] };
                    }
                    pendingNode.subAgents[currentAgentName].events.push(node);
                } else {
                    tree.push(node);
                }
                break;
            }
        }
    }

    return tree;
}

// ===== Actions =====

export function addEvent(evt) {
    setState({ events: [...state.events, evt] });
}

export function resetView() {
    setState({
        events: [],
        status: { message: '', type: '' },
        sessionId: null,
        isRunning: false,
        isStopped: false,
        finalAnswer: null,
        totalStartTime: null,
        viewingLiveSession: false,
    });
    currentReader = null;
    cachedEvents = null;
    cachedTree = [];
}

// ===== Multi-Session SSE Stream =====

// Single reader for live/background mode (one at a time)
let currentReader = null;

// Per-session event buffers for auto-kill mode (multiple simultaneous SSE connections)
// { sessionId: { events: [], reader, question, model, finalAnswer, hasError, startTime } }
const liveSessions = {};

/** Check if a session has an active SSE connection in liveSessions */
export function isSessionLive(sessionId) {
    return sessionId in liveSessions;
}

/**
 * Kill sessions that should die on page unload (auto-kill + live modes).
 * Uses sendBeacon for reliability during tab close.
 * Background persistent sessions are NOT killed.
 */
export function handlePageUnload() {
    // Kill all auto-kill sessions
    for (const sid of Object.keys(liveSessions)) {
        navigator.sendBeacon(`/api/stop/${sid}`, '');
    }

    // Kill the current live-mode session (uses blocking reader, not liveSessions)
    if (state.runMode === 'live' && (state.isRunning || state.viewingLiveSession)) {
        const sid = state.activeSessionId || state.sessionId;
        if (sid) {
            navigator.sendBeacon(`/api/stop/${sid}`, '');
        }
    }
}

/** Get count of active live sessions */
export function getLiveSessionIds() {
    return Object.keys(liveSessions);
}

export async function loadModels() {
    try {
        const response = await fetch('/api/models');
        if (!response.ok) throw new Error('Failed to load models');
        const data = await response.json();
        setState({
            models: data,
            selectedModel: data.length > 0 && !state.selectedModel ? data[0].id : state.selectedModel,
        });
    } catch (e) {
        console.error('Failed to load models:', e);
        setState({
            models: [{ id: 'o1', name: 'OpenAI o1', description: 'Advanced reasoning' }],
            selectedModel: state.selectedModel || 'o1',
        });
    }
}

export function setRunMode(mode) {
    if (!['background', 'auto-kill', 'live'].includes(mode)) return;
    setState({ runMode: mode });
    localStorage.setItem('odr-run-mode', mode);
}

// ===== SSE Parsing Helpers =====

/**
 * Parse SSE lines from a buffer, calling onEvent for each parsed JSON event.
 * Returns the remaining incomplete line (buffer remainder).
 */
function parseSSELines(buffer, onEvent) {
    const lines = buffer.split('\n');
    for (let i = 0; i < lines.length - 1; i++) {
        const line = lines[i];
        if (line.startsWith('data: ')) {
            try {
                onEvent(JSON.parse(line.slice(6)));
            } catch (e) {
                console.error('Failed to parse SSE:', line.slice(6), e);
            }
        }
    }
    return lines[lines.length - 1];
}

/**
 * Extract session_id from an SSE response (reads until session_id found, then stops).
 */
async function extractSessionId(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let sessionId = null;
        buffer = parseSSELines(buffer, (data) => {
            if (data.session_id) sessionId = data.session_id;
        });
        if (sessionId) return sessionId;
    }
    return null;
}

// ===== Mode-specific stream readers =====

/**
 * Read a coupled SSE stream for LIVE mode (single session, blocks UI).
 * Used by live mode and for background /live reconnect.
 */
async function readBlockingSSEStream(response) {
    const reader = response.body.getReader();
    currentReader = reader;
    const decoder = new TextDecoder();
    let buffer = '';
    let hasError = false;

    try {
        while (true) {
            if (state.isStopped) break;
            const { done, value } = await reader.read();

            if (done) {
                setState({
                    status: {
                        message: hasError ? 'Completed with errors' : 'Completed successfully',
                        type: hasError ? 'error' : 'success',
                    },
                });
                break;
            }

            buffer += decoder.decode(value, { stream: true });
            let shouldBreak = false;
            buffer = parseSSELines(buffer, (jsonData) => {
                if (shouldBreak) return;
                if (jsonData.session_id) {
                    setState({ sessionId: jsonData.session_id, activeSessionId: jsonData.session_id });
                    loadSessions();
                } else if (jsonData.done) {
                    setState({
                        status: {
                            message: hasError ? 'Completed with errors' : 'Completed successfully',
                            type: hasError ? 'error' : 'success',
                        },
                    });
                    shouldBreak = true;
                } else {
                    addEvent(jsonData);
                    if (jsonData.type === 'error') hasError = true;
                    if (jsonData.type === 'final_answer' && !jsonData.agent_name) {
                        setState({ finalAnswer: jsonData.output || jsonData.content });
                    }
                }
            });
            if (shouldBreak) break;
        }
    } finally {
        currentReader = null;
    }
}

/**
 * Start a background SSE reader for auto-kill mode.
 * Events accumulate in liveSessions[sessionId].events.
 * If sessionId is currently viewed, state.events is updated in real-time.
 * Runs as a fire-and-forget async task — does NOT block.
 * @param {string} sessionId
 * @param {ReadableStreamDefaultReader} reader — the SSE stream reader (may already have been partially consumed for session_id extraction)
 */
function startAutoKillStream(sessionId, reader) {
    const decoder = new TextDecoder();
    const session = liveSessions[sessionId];
    session.reader = reader;

    (async () => {
        let buffer = '';
        try {
            while (true) {
                if (session.stopped) break;
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                let shouldBreak = false;
                buffer = parseSSELines(buffer, (jsonData) => {
                    if (shouldBreak) return;
                    if (jsonData.session_id) {
                        // Already have session_id
                    } else if (jsonData.done) {
                        shouldBreak = true;
                    } else {
                        session.events.push(jsonData);
                        if (jsonData.type === 'error') session.hasError = true;
                        if (jsonData.type === 'final_answer' && !jsonData.agent_name) {
                            session.finalAnswer = jsonData.output || jsonData.content;
                        }
                        // If this session is currently viewed, update the display
                        if (state.activeSessionId === sessionId) {
                            cachedEvents = null;
                            cachedTree = [];
                            setState({
                                events: [...session.events],
                                finalAnswer: session.finalAnswer,
                            });
                        }
                    }
                });
                if (shouldBreak) break;
            }
        } catch (e) {
            if (!session.stopped) {
                console.error(`Auto-kill stream error for ${sessionId}:`, e);
            }
        } finally {
            session.reader = null;
            const wasViewing = state.activeSessionId === sessionId;

            // Update status if viewing this session
            if (wasViewing) {
                setState({
                    viewingLiveSession: false,
                    status: {
                        message: session.stopped ? 'Stopped by user'
                            : session.hasError ? 'Completed with errors' : 'Completed successfully',
                        type: session.stopped || session.hasError ? 'error' : 'success',
                    },
                });
            }

            delete liveSessions[sessionId];
            loadSessions();
        }
    })();
}

/**
 * Connect to /live SSE endpoint for background persistent mode.
 */
async function connectToLiveStream(sessionId, afterOrder = -1) {
    const url = afterOrder >= 0
        ? `/api/sessions/${sessionId}/live?after_order=${afterOrder}`
        : `/api/sessions/${sessionId}/live`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to connect to live stream');
    await readBlockingSSEStream(response);
}

// ===== Public Actions =====

export async function startStream() {
    const q = state.question.trim();
    if (!q) {
        setState({ status: { message: 'Please enter a question', type: 'error' } });
        return;
    }

    const model = state.selectedModel;
    const mode = state.runMode;

    const apiKeys = getClientApiKeys();

    if (mode === 'auto-kill') {
        // Auto-kill: fire-and-forget, don't block UI
        setState({
            status: { message: 'Starting agent...', type: 'loading' },
        });

        try {
            const response = await fetch('/api/run/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: q, model_id: model, run_mode: mode, api_keys: apiKeys }),
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'Unknown error' }));
                setState({ status: { message: `Error: ${error.error || 'Unknown error'}`, type: 'error' } });
                return;
            }

            // Read the SSE stream to find session_id in the first message,
            // then continue reading events in the background
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let sessionId = null;

            // Read until we get session_id
            while (!sessionId) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                buffer = parseSSELines(buffer, (data) => {
                    if (data.session_id) sessionId = data.session_id;
                });
            }

            if (!sessionId) {
                setState({ status: { message: 'Failed to get session ID', type: 'error' } });
                return;
            }

            // Register in liveSessions
            liveSessions[sessionId] = {
                events: [],
                reader: null,
                question: q,
                model: model,
                finalAnswer: null,
                hasError: false,
                stopped: false,
                startTime: Date.now(),
            };

            // Switch view to this session
            cachedEvents = null;
            cachedTree = [];
            setState({
                events: [],
                question: q,
                selectedModel: model,
                sessionId: sessionId,
                activeSessionId: sessionId,
                viewingHistory: false,
                isRunning: false,  // UI not locked in auto-kill mode
                isStopped: false,
                finalAnswer: null,
                totalStartTime: Date.now(),
                viewingLiveSession: true,
                status: { message: 'Running agent...', type: 'loading' },
            });

            loadSessions();

            // Process any events that were in the same chunk as session_id
            const remainingEvents = [];
            parseSSELines(buffer, (data) => {
                if (!data.session_id && !data.done) {
                    remainingEvents.push(data);
                }
            });
            for (const evt of remainingEvents) {
                liveSessions[sessionId].events.push(evt);
            }
            if (remainingEvents.length > 0 && state.activeSessionId === sessionId) {
                setState({ events: [...liveSessions[sessionId].events] });
            }

            // Continue reading in background
            startAutoKillStream(sessionId, reader);

        } catch (error) {
            setState({ status: { message: `Connection Error: ${error.message}`, type: 'error' } });
        }
        return;
    }

    // Background persistent or Live mode — blocks the view
    resetView();
    setState({
        question: q,
        selectedModel: model,
        runMode: mode,
        isRunning: mode === 'live',  // Only live mode locks the UI
        totalStartTime: Date.now(),
        status: { message: 'Running agent...', type: 'loading' },
        viewingHistory: false,
        viewingLiveSession: true,
        activeSessionId: null,
    });

    try {
        const response = await fetch('/api/run/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q, model_id: model, run_mode: mode, api_keys: apiKeys }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            setState({
                status: { message: `Error: ${error.error || 'Unknown error'}`, type: 'error' },
                isRunning: false,
                viewingLiveSession: false,
            });
            return;
        }

        if (mode === 'live') {
            // Live: coupled SSE, blocks UI
            await readBlockingSSEStream(response);
        } else {
            // Background persistent: extract session_id, connect to /live
            const sessionId = await extractSessionId(response);
            if (sessionId) {
                setState({ sessionId, activeSessionId: sessionId });
                loadSessions();
                await connectToLiveStream(sessionId);
            }
        }
    } catch (error) {
        if (!state.isStopped) {
            setState({ status: { message: `Connection Error: ${error.message}`, type: 'error' } });
        }
    } finally {
        setState({ isRunning: false, viewingLiveSession: false });
        currentReader = null;
        loadSessions();
        if (state.sessionId) {
            setState({ activeSessionId: state.sessionId });
        }
    }
}

/**
 * Stop a specific session's agent. Works for all modes.
 */
export async function stopSession(sessionId) {
    if (!sessionId) sessionId = state.activeSessionId || state.sessionId;
    if (!sessionId) return;

    // Stop via API
    try {
        await fetch(`/api/stop/${sessionId}`, { method: 'POST' });
    } catch (error) {
        console.error('Error stopping session:', error);
    }

    // If it's an auto-kill live session, cancel its reader
    if (liveSessions[sessionId]) {
        liveSessions[sessionId].stopped = true;
        if (liveSessions[sessionId].reader) {
            try { liveSessions[sessionId].reader.cancel(); } catch (e) { /* ignore */ }
        }
    }

    // If it's the current blocking reader (live/background mode)
    if (currentReader) {
        setState({ isStopped: true });
        try { currentReader.cancel(); } catch (e) { /* ignore */ }
        currentReader = null;
    }

    // Update UI if viewing this session
    if (state.activeSessionId === sessionId || state.sessionId === sessionId) {
        addEvent({ type: 'error', content: 'Agent execution cancelled by user' });
        setState({
            status: { message: 'Stopped by user', type: 'error' },
            isRunning: false,
            viewingLiveSession: false,
        });
    }

    loadSessions();
}

// Keep backward-compatible export
export async function stopStream() {
    await stopSession(state.activeSessionId || state.sessionId);
}

/**
 * Disconnect from a background persistent session's /live stream without killing the agent.
 */
function disconnectLiveStream() {
    if (currentReader) {
        setState({ isStopped: true });
        try { currentReader.cancel(); } catch (e) { /* ignore */ }
        currentReader = null;
    }
    setState({ isRunning: false, viewingLiveSession: false });
}

/**
 * Switch the view to show a different auto-kill session's events (instant, no network).
 */
function switchToLiveSession(sessionId) {
    const session = liveSessions[sessionId];
    if (!session) return false;

    cachedEvents = null;
    cachedTree = [];
    setState({
        events: [...session.events],
        question: session.question,
        selectedModel: session.model,
        sessionId: sessionId,
        activeSessionId: sessionId,
        viewingHistory: false,
        isRunning: false,
        isStopped: false,
        finalAnswer: session.finalAnswer,
        totalStartTime: session.startTime,
        viewingLiveSession: !!session.reader,
        status: session.reader
            ? { message: 'Running agent...', type: 'loading' }
            : {
                message: session.hasError ? 'Completed with errors' : 'Completed successfully',
                type: session.hasError ? 'error' : 'success',
            },
    });
    return true;
}

export function toggleTheme() {
    const next = state.theme === 'dark' ? 'light' : 'dark';
    setState({ theme: next });
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('odr-theme', next);

    const hlLink = document.getElementById('highlight-theme');
    if (hlLink) {
        hlLink.href = next === 'dark'
            ? 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css'
            : 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
    }
}

// ===== Session Management =====

export async function loadSessions() {
    setState({ sessionsLoading: true });
    try {
        const response = await fetch('/api/sessions?limit=50');
        if (!response.ok) throw new Error('Failed to load sessions');
        const data = await response.json();
        setState({ sessions: data, sessionsLoading: false });
    } catch (e) {
        console.error('Failed to load sessions:', e);
        setState({ sessionsLoading: false });
    }
}

export async function loadSession(sessionId) {
    if (state.activeSessionId === sessionId) return;

    // If it's an auto-kill session we already have in memory — instant switch
    if (liveSessions[sessionId]) {
        switchToLiveSession(sessionId);
        return;
    }

    // In live mode while running, block session switching (UI should prevent this too)
    if (state.isRunning && state.runMode === 'live') return;

    // If currently viewing a background persistent /live stream, disconnect viewer (agent keeps running)
    if (currentReader) {
        disconnectLiveStream();
    }

    setState({ status: { message: 'Loading session...', type: 'loading' } });

    try {
        const response = await fetch(`/api/sessions/${sessionId}`);
        if (!response.ok) throw new Error('Session not found');
        const session = await response.json();

        cachedEvents = null;
        cachedTree = [];

        // If session is still running (background persistent), reconnect via /live
        if (session.status === 'running') {
            const eventCount = (session.events || []).length;
            setState({
                events: session.events || [],
                question: session.question,
                selectedModel: session.model_id,
                sessionId: sessionId,
                activeSessionId: sessionId,
                viewingHistory: false,
                isRunning: false,
                isStopped: false,
                finalAnswer: null,
                totalStartTime: Date.now(),
                viewingLiveSession: true,
                status: { message: 'Reconnected to running agent...', type: 'loading' },
            });

            try {
                await connectToLiveStream(sessionId, eventCount - 1);
            } catch (e) {
                console.error('Failed to reconnect:', e);
                setState({ status: { message: `Reconnect failed: ${e.message}`, type: 'error' } });
            } finally {
                setState({ isRunning: false, viewingLiveSession: false });
                currentReader = null;
                loadSessions();
            }
            return;
        }

        // Not running — show history
        setState({
            events: session.events || [],
            question: session.question,
            selectedModel: session.model_id,
            sessionId: sessionId,
            activeSessionId: sessionId,
            viewingHistory: true,
            isRunning: false,
            isStopped: false,
            finalAnswer: session.final_answer || null,
            viewingLiveSession: false,
            status: {
                message: `Session from ${new Date(session.created_at).toLocaleString()} (${session.status})`,
                type: session.status === 'completed' ? 'success' : 'error',
            },
            totalStartTime: null,
        });
    } catch (e) {
        setState({
            status: { message: `Error loading session: ${e.message}`, type: 'error' },
        });
    }
}

export async function deleteSession(sessionId) {
    // If it's a live auto-kill session, stop it first
    if (liveSessions[sessionId]) {
        await stopSession(sessionId);
    }

    try {
        const response = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete');

        setState({
            sessions: state.sessions.filter(s => s.id !== sessionId),
        });

        if (state.activeSessionId === sessionId) {
            resetView();
            setState({ question: '', activeSessionId: null, viewingHistory: false });
        }
    } catch (e) {
        console.error('Failed to delete session:', e);
    }
}

export async function newSession() {
    // In live mode while running, block new session (UI should prevent this too)
    if (state.isRunning && state.runMode === 'live') return;

    // If currently viewing a background /live stream, disconnect viewer (agent keeps running)
    if (currentReader) {
        disconnectLiveStream();
    }

    // For auto-kill: existing sessions keep streaming in background, just clear the view
    resetView();
    setState({ question: '', activeSessionId: null, viewingHistory: false });
}

export function toggleSidebar() {
    setState({ sidebarOpen: !state.sidebarOpen });
}

export function toggleSettings() {
    setState({ settingsOpen: !state.settingsOpen });
}

export async function loadConfigMeta() {
    try {
        const response = await fetch('/api/config/meta');
        if (response.ok) {
            const data = await response.json();
            setState({ enableConfigUI: data.enable_config_ui });
        }
    } catch (e) {
        console.error('Failed to load config meta:', e);
    }
}

/** Read client API keys from localStorage */
export function getClientApiKeys() {
    const keys = {};
    const keyNames = ['openai', 'deepseek', 'serpapi', 'meta_sota', 'hf_token'];
    for (const k of keyNames) {
        const val = localStorage.getItem(`odr-apikey-${k}`);
        if (val) keys[k] = val;
    }
    return keys;
}

/**
 * Called when the page becomes visible again (e.g. tab restored from bfcache,
 * or user switches back to this tab). Refreshes sidebar and reloads the
 * active session from DB so stale in-memory state is replaced.
 */
export async function handlePageVisible() {
    loadSessions();

    const sid = state.activeSessionId;
    if (!sid) return;

    // If it's an auto-kill session still in memory with a live reader, leave it alone
    if (liveSessions[sid] && liveSessions[sid].reader) return;

    // Reload session from DB to get the true state
    try {
        const resp = await fetch(`/api/sessions/${sid}`);
        if (!resp.ok) return;
        const session = await resp.json();

        // Cancel any stale reader
        if (currentReader) {
            try { currentReader.cancel(); } catch (e) { /* ignore */ }
            currentReader = null;
        }

        // Clean up stale auto-kill entry
        if (liveSessions[sid]) {
            delete liveSessions[sid];
        }

        cachedEvents = null;
        cachedTree = [];

        if (session.status === 'running') {
            // Still running — reconnect
            setState({
                events: session.events || [],
                viewingLiveSession: true,
                isRunning: false,
                finalAnswer: null,
                status: { message: 'Reconnected to running agent...', type: 'loading' },
            });
            try {
                await connectToLiveStream(sid, (session.events || []).length - 1);
            } catch (e) {
                console.error('Reconnect failed:', e);
            } finally {
                setState({ isRunning: false, viewingLiveSession: false });
                currentReader = null;
                loadSessions();
            }
        } else {
            // Session ended — show final state from DB
            setState({
                events: session.events || [],
                viewingLiveSession: false,
                isRunning: false,
                isStopped: false,
                finalAnswer: session.final_answer || null,
                viewingHistory: true,
                status: {
                    message: `Session ${session.status}`,
                    type: session.status === 'completed' ? 'success' : 'error',
                },
            });
        }
    } catch (e) {
        console.error('Failed to refresh session:', e);
    }
}

