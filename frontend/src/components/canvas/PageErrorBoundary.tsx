// frontend/src/components/canvas/PageErrorBoundary.tsx
//
// Wraps each PageRenderer so a single page failure (render crash, hook throw)
// doesn't bring down the entire canvas. The failed page shows a lightweight
// error card; all other pages continue to render normally.

import React, { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  pageIndex: number;
  children:  ReactNode;
}

interface State {
  error:   Error | null;
  eventId: string | null;
}

export class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null, eventId: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, eventId: Math.random().toString(36).slice(2, 8) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log for debugging — swap for Sentry/Datadog call if you have one
    console.error(
      `[PageErrorBoundary] page ${this.props.pageIndex + 1} crashed`,
      error,
      info.componentStack,
    );
  }

  reset = () => this.setState({ error: null, eventId: null });

  render() {
    if (this.state.error) {
      return (
        <PageErrorCard
          pageIndex={this.props.pageIndex}
          message={this.state.error.message}
          onRetry={this.reset}
        />
      );
    }
    return this.props.children;
  }
}

// ── Fallback UI ────────────────────────────────────────────────────────────

interface PageErrorCardProps {
  pageIndex: number;
  message:   string;
  onRetry:   () => void;
}

function PageErrorCard({ pageIndex, message, onRetry }: PageErrorCardProps) {
  return (
    <div
      className="relative bg-white flex-shrink-0 mx-auto mb-6 rounded-sm shadow-xl flex flex-col items-center justify-center gap-3 select-none"
      style={{ width: 595, height: 842 }} // A4 at 72dpi — matches default page size
    >
      <div className="text-red-400 text-4xl">⚠</div>
      <p className="text-sm font-semibold text-gray-700">
        Page {pageIndex + 1} failed to render
      </p>
      <p className="text-xs text-gray-400 max-w-[260px] text-center leading-relaxed">
        {message}
      </p>
      <button
        onClick={onRetry}
        className="mt-1 h-7 px-4 bg-[#4a90e2] text-white text-xs font-semibold rounded-md hover:bg-[#3a7fd2] transition-colors"
      >
        Retry
      </button>
    </div>
  );
}