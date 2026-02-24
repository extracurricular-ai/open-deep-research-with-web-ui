/**
 * HTM (Hyperscript Tagged Markup) setup for Preact
 * Provides the html`` tagged template literal as a JSX alternative
 */
import { h } from 'preact';
import htm from 'htm';

export const html = htm.bind(h);
