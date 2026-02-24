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

export function resetState() {
    setState({
        events: [],
        status: { message: '', type: '' },
        sessionId: null,
        isRunning: false,
        isStopped: false,
        finalAnswer: null,
        totalStartTime: null,
    });
    currentReader = null;
    cachedEvents = null;
    cachedTree = [];
}

// ===== SSE Stream =====
let currentReader = null;

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

export async function startStream() {
    const q = state.question.trim();
    if (!q) {
        setState({ status: { message: 'Please enter a question', type: 'error' } });
        return;
    }

    const model = state.selectedModel;
    resetState();
    setState({
        question: q,
        selectedModel: model,
        isRunning: true,
        totalStartTime: Date.now(),
        status: { message: 'Running agent...', type: 'loading' },
    });

    let hasError = false;

    try {
        const response = await fetch('/api/run/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q, model_id: model }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            setState({
                status: { message: `Error: ${error.error || 'Unknown error'}`, type: 'error' },
                isRunning: false,
            });
            return;
        }

        const reader = response.body.getReader();
        currentReader = reader;
        const decoder = new TextDecoder();
        let buffer = '';

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
            const lines = buffer.split('\n');

            for (let i = 0; i < lines.length - 1; i++) {
                const line = lines[i];
                if (line.startsWith('data: ')) {
                    const jsonStr = line.slice(6);
                    try {
                        const jsonData = JSON.parse(jsonStr);

                        if (jsonData.session_id) {
                            setState({ sessionId: jsonData.session_id });
                        } else if (jsonData.done) {
                            break;
                        } else {
                            addEvent(jsonData);
                            if (jsonData.type === 'error') {
                                hasError = true;
                            }
                            if (jsonData.type === 'final_answer' && !jsonData.agent_name) {
                                setState({ finalAnswer: jsonData.output || jsonData.content });
                            }
                        }
                    } catch (parseErr) {
                        console.error('Failed to parse:', jsonStr, parseErr);
                    }
                }
            }

            buffer = lines[lines.length - 1];
        }
    } catch (error) {
        setState({ status: { message: `Connection Error: ${error.message}`, type: 'error' } });
    } finally {
        setState({ isRunning: false });
        currentReader = null;

        saveToHistory(q, model, state.finalAnswer);
    }
}

export async function stopStream() {
    if (currentReader && state.sessionId) {
        setState({ isStopped: true });

        try {
            await fetch(`/api/stop/${state.sessionId}`, { method: 'POST' });
        } catch (error) {
            console.error('Error stopping session:', error);
        }

        currentReader.cancel();
        currentReader = null;

        addEvent({ type: 'error', content: 'Agent execution cancelled by user' });
        setState({ status: { message: 'Stopped by user', type: 'error' }, isRunning: false });
    }
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

// ===== History Management =====
const HISTORY_KEY = 'open_deep_research_history';
const MAX_HISTORY = 20;

function saveToHistory(questionText, modelId, answer) {
    const history = getHistory();
    history.unshift({
        id: Date.now(),
        question: questionText,
        modelId: modelId,
        timestamp: new Date().toISOString(),
        finalAnswer: answer ? answer.substring(0, 500) : null,
    });
    if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;
    try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (e) {
        history.length = Math.floor(MAX_HISTORY / 2);
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    }
}

export function getHistory() {
    try {
        return JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
    } catch {
        return [];
    }
}

export function clearHistory() {
    localStorage.removeItem(HISTORY_KEY);
}
