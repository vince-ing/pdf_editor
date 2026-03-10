// frontend/src/hooks/useSearchState.ts
import { useState, useCallback, useRef, useEffect } from 'react';
import { engineApi } from '../api/client';
import type { DocumentState } from '../components/canvas/types';

export interface SearchMatch {
  pageIndex: number;
  pageId: string;
  rects: { x: number; y: number; width: number; height: number }[];
  text: string;
  // Context snippet: text immediately before/after the match on the page
  contextBefore: string;
  contextAfter:  string;
}

// Map from pageId -> array of rect-groups (each group = one match on that page)
export type PageMatchMap = Record<string, {
  rects:      { x: number; y: number; width: number; height: number }[];
  matchIndex: number;
  isCurrent:  boolean;
}[]>;

interface UseSearchStateArgs {
  documentState:   DocumentState | null;
  sessionId:       string | null;
  pageRefs:        React.MutableRefObject<(HTMLDivElement | null)[]>;
  canvasScrollRef: React.MutableRefObject<HTMLDivElement | null>;
  scale:           number;
}

const CONTEXT_CHARS = 40;

export function useSearchState({
  documentState, sessionId, pageRefs, canvasScrollRef, scale,
}: UseSearchStateArgs) {
  const [isOpen,         setIsOpen]         = useState(false);
  const inputRef                             = useRef<HTMLInputElement>(null);
  const [query,          setQuery]          = useState('');
  const [matches,        setMatches]        = useState<SearchMatch[]>([]);
  const [currentIndex,   setCurrentIndex]   = useState(-1);
  const [isSearching,    setIsSearching]    = useState(false);
  const [pageCharsCache, setPageCharsCache] = useState<Record<string, any[]>>({});
  const abortRef  = useRef(false);
  const scaleRef  = useRef(scale);
  useEffect(() => { scaleRef.current = scale; }, [scale]);

  // ── pageMatchMap ────────────────────────────────────────────────────────────
  const pageMatchMap: PageMatchMap = {};
  matches.forEach((match, i) => {
    if (!pageMatchMap[match.pageId]) pageMatchMap[match.pageId] = [];
    pageMatchMap[match.pageId].push({
      rects:      match.rects,
      matchIndex: i,
      isCurrent:  i === currentIndex,
    });
  });

  // ── Reset on document change ────────────────────────────────────────────────
  useEffect(() => {
    setPageCharsCache({});
    setMatches([]);
    setQuery('');
    setCurrentIndex(-1);
  }, [documentState?.file_name]);

  // ── Char loading ────────────────────────────────────────────────────────────
  const loadPageChars = useCallback(async (pageId: string, sid: string) => {
    if (pageCharsCache[pageId]) return pageCharsCache[pageId];
    try {
      const chars = await engineApi.getPageChars(pageId, sid);
      setPageCharsCache(prev => ({ ...prev, [pageId]: chars }));
      return chars;
    } catch { return []; }
  }, [pageCharsCache]);

  // ── Core search ─────────────────────────────────────────────────────────────
  const runSearch = useCallback(async (q: string) => {
    if (!q.trim() || !documentState?.children || !sessionId) {
      setMatches([]); setCurrentIndex(-1); return;
    }
    setIsSearching(true);
    abortRef.current = false;
    const lower      = q.toLowerCase();
    const allMatches: SearchMatch[] = [];

    try {
      for (let pi = 0; pi < documentState.children.length; pi++) {
        if (abortRef.current) break;
        const page  = documentState.children[pi];
        const chars = await loadPageChars(page.id, sessionId);
        if (!chars?.length) continue;

        const fullText  = chars.map((c: any) => c.text).join('');
        const fullLower = fullText.toLowerCase();
        let   searchIdx = 0;

        while (true) {
          const foundAt = fullLower.indexOf(lower, searchIdx);
          if (foundAt === -1) break;

          // Merge match chars into per-line bounding rects
          const matchChars = chars.slice(foundAt, foundAt + q.length);
          const lineMap: Record<number, { x: number; y: number; width: number; height: number }> = {};
          for (const ch of matchChars) {
            const key = Math.round(ch.y);
            if (!lineMap[key]) {
              lineMap[key] = { x: ch.x, y: ch.y, width: ch.width, height: ch.height };
            } else {
              const e = lineMap[key];
              const right = Math.max(e.x + e.width, ch.x + ch.width);
              e.x     = Math.min(e.x, ch.x);
              e.width = right - e.x;
              e.height = Math.max(e.height, ch.height);
            }
          }

          const rects = Object.values(lineMap);
          if (rects.length > 0) {
            const ctxStart = Math.max(0, foundAt - CONTEXT_CHARS);
            const ctxEnd   = Math.min(fullText.length, foundAt + q.length + CONTEXT_CHARS);
            allMatches.push({
              pageIndex:     pi,
              pageId:        page.id,
              rects,
              text:          fullText.slice(foundAt, foundAt + q.length),
              contextBefore: fullText.slice(ctxStart, foundAt),
              contextAfter:  fullText.slice(foundAt + q.length, ctxEnd),
            });
          }
          searchIdx = foundAt + 1;
        }
      }

      setMatches(allMatches);
      setCurrentIndex(allMatches.length > 0 ? 0 : -1);
    } finally {
      setIsSearching(false);
    }
  }, [documentState, sessionId, loadPageChars]);

  // ── Precise rect-level scroll ───────────────────────────────────────────────
  const scrollToMatchRect = useCallback((index: number, matchList?: SearchMatch[]) => {
    const list = matchList ?? matches;
    if (index < 0 || index >= list.length) return;
    const match    = list[index];
    const pageEl   = pageRefs.current[match.pageIndex];
    const scrollEl = canvasScrollRef.current;
    if (!pageEl || !scrollEl) return;

    const sc   = scaleRef.current;
    const rect = match.rects[0]; // top-most line of the match

    // Absolute position of rect inside the scroll container
    const absTop    = pageEl.offsetTop  + rect.y * sc;
    const absLeft   = pageEl.offsetLeft + rect.x * sc;
    const absBottom = absTop  + rect.height * sc;
    const absRight  = absLeft + rect.width  * sc;

    const pad       = 80; // breathing room in px
    const visTop    = scrollEl.scrollTop;
    const visBottom = visTop  + scrollEl.clientHeight;
    const visLeft   = scrollEl.scrollLeft;
    const visRight  = visLeft + scrollEl.clientWidth;

    const outOfView =
      absTop    < visTop    + pad ||
      absBottom > visBottom - pad ||
      absLeft   < visLeft   + pad ||
      absRight  > visRight  - pad;

    if (outOfView) {
      scrollEl.scrollTo({
        top:      Math.max(0, absTop  - scrollEl.clientHeight  / 2 + (rect.height * sc) / 2),
        left:     Math.max(0, absLeft - scrollEl.clientWidth   / 2 + (rect.width  * sc) / 2),
        behavior: 'smooth',
      });
    }
  }, [matches, pageRefs, canvasScrollRef]);

  // ── goToMatch — single navigation entry point ───────────────────────────────
  const goToMatch = useCallback((index: number) => {
    if (!matches.length) return;
    const clamped = ((index % matches.length) + matches.length) % matches.length;
    setCurrentIndex(clamped);
    scrollToMatchRect(clamped);
  }, [matches, scrollToMatchRect]);

  const goNext = useCallback(() => goToMatch(currentIndex + 1), [goToMatch, currentIndex]);
  const goPrev = useCallback(() => goToMatch(currentIndex - 1), [goToMatch, currentIndex]);

  // ── open / close ────────────────────────────────────────────────────────────
  const open = useCallback(() => {
    setIsOpen(true);
    setTimeout(() => inputRef.current?.focus(), 60);
  }, []);

  const close = useCallback(() => {
    abortRef.current = true;
    setIsOpen(false);
    setQuery('');
    setMatches([]);
    setCurrentIndex(-1);
  }, []);

  // ── Debounced query handler ─────────────────────────────────────────────────
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const handleQueryChange = useCallback((q: string) => {
    setQuery(q);
    clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setIsSearching(false);
      setMatches([]);
      setCurrentIndex(-1);
      return;
    }
    // Mark as searching immediately so the UI never flashes "no results"
    // during the debounce delay
    setIsSearching(true);
    debounceRef.current = setTimeout(() => runSearch(q), 300);
  }, [runSearch]);

  // Scroll to first match when a new search completes
  const prevMatchCountRef = useRef(0);
  useEffect(() => {
    if (matches.length > 0 && matches.length !== prevMatchCountRef.current) {
      scrollToMatchRect(0, matches);
    }
    prevMatchCountRef.current = matches.length;
  }, [matches, scrollToMatchRect]);

  return {
    isOpen, open, close,
    query, handleQueryChange,
    matches, currentIndex,
    pageMatchMap,
    isSearching,
    goNext, goPrev,
    goToMatch,
    inputRef,
  };
}