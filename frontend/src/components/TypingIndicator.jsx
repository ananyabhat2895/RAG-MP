import React from 'react';

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 my-4 max-w-3xl mx-auto px-2 sm:px-4">
      {/* Botanical avatar */}
      <div className="w-7 h-7 rounded-md bg-[#1c3829] text-[#e8f0ec] flex items-center justify-center flex-shrink-0 mt-0.5 shadow-xs">
        <svg
          className="w-3.5 h-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
          <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
        </svg>
      </div>

      <div className="pt-1">
        <div className="flex items-center gap-2 py-1 px-1">
          <span className="text-xs text-[#526a5c] font-medium">RAG-MP is thinking</span>
          <div className="flex items-center gap-1">
            <span
              className="w-1.5 h-1.5 rounded-full bg-[#3e5e4b] animate-bounce"
              style={{ animationDelay: '0ms', animationDuration: '900ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-[#3e5e4b] animate-bounce"
              style={{ animationDelay: '150ms', animationDuration: '900ms' }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-[#3e5e4b] animate-bounce"
              style={{ animationDelay: '300ms', animationDuration: '900ms' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
