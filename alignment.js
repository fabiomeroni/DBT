/* The alignment of an interlinear sentence: the words of each language in columns, and one gloss for each column.
 *
 *   state = { tokens: { lang: [word, word, ...] }, glosses: [gloss, ...], n: number of columns }
 *
 * The editor of the Texts page works on such a state. Every function changes the state it is given (the rows of all the languages and the row of the
 * glosses always keep the same length, n) and says what it did. No page, no network: the rules of the editing are here, so that they can be tested.
 */
(function (root) {
  'use strict';

  // a place with no word: nothing, spaces, or the dash that stands for a missing word
  const isEmpty = v => v === undefined || v === null || String(v).trim() === '' || String(v).trim() === '—';

  /** Make every row as long as n (the rows of the languages, and the glosses). */
  function pad(state) {
    Object.keys(state.tokens).forEach(l => { const r = state.tokens[l]; while (r.length < state.n) r.push(''); });
    while (state.glosses.length < state.n) state.glosses.push('');
    return state;
  }

  /** Insert an empty column so that it becomes column `at` (0 = before the first, n = after the last). Returns the index of the new column. */
  function insertColumn(state, at) {
    pad(state);
    at = Math.max(0, Math.min(state.n, Number.isInteger(at) ? at : state.n));
    Object.keys(state.tokens).forEach(l => state.tokens[l].splice(at, 0, ''));
    state.glosses.splice(at, 0, '');
    state.n++;
    return at;
  }

  /** Delete column `at` (the last remaining column cannot be deleted). Returns true if it was deleted. */
  function deleteColumn(state, at) {
    pad(state);
    if (state.n <= 1 || !Number.isInteger(at) || at < 0 || at >= state.n) return false;
    Object.keys(state.tokens).forEach(l => state.tokens[l].splice(at, 1));
    state.glosses.splice(at, 1);
    state.n--;
    return true;
  }

  /** Can the word at (lang, from) be dropped on (lang, to)? Only inside one language, from a place that has a word, to another place of the row. */
  function canMove(state, lang, from, to) {
    const row = state.tokens[lang];
    return !!row && Number.isInteger(from) && Number.isInteger(to) && from !== to && from >= 0 && to >= 0 && from < state.n && to < state.n && !isEmpty(row[from]);
  }

  /**
   * Move the word at (lang, from) to (lang, to). Only that word of that language moves; the glosses and the other languages stay where they are.
   *  - an empty place: the word goes there, and its old place is left empty;
   *  - an occupied place: the word that is there, and the words that follow it without a gap, go one place to the right (the first empty place takes up
   *    the shift: what is after it does not move); if there is no empty place before the end of the row, a column is added at the end for them.
   * Returns { moved, shifted (how many words were pushed right), created (a column was added) }.
   */
  function moveToken(state, lang, from, to) {
    pad(state);
    if (!canMove(state, lang, from, to)) return { moved: false, shifted: 0, created: false };
    const row = state.tokens[lang], word = row[from];
    row[from] = '';                                              // the word leaves its place (which may then take up the shift, when it is to the right)
    if (isEmpty(row[to])) { row[to] = word; return { moved: true, shifted: 0, created: false }; }
    let k = to;
    while (k < state.n && !isEmpty(row[k])) k++;                 // the first empty place after the destination
    let created = false;
    if (k === state.n) { insertColumn(state, state.n); created = true; }
    for (let m = k; m > to; m--) row[m] = row[m - 1];
    row[to] = word;
    return { moved: true, shifted: k - to, created };
  }

  const api = { isEmpty, pad, insertColumn, deleteColumn, canMove, moveToken };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.Alignment = api;
})(typeof window !== 'undefined' ? window : this);
