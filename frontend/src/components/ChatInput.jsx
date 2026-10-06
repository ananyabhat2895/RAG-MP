import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp } from 'lucide-react';

export default function ChatInput({ onSendMessage, isLoading, autoFocusKey }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  // Auto-focus when requested (e.g. on mount or new chat created)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [autoFocusKey]);

  // Dynamically auto-resize textarea up to 140px
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    onSendMessage(trimmed);
    setText('');

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    // Ignore IME composition
    if (e.nativeEvent.isComposing) return;

    if (e.key === 'Enter') {
      if (e.shiftKey) {
        // Shift + Enter: creates new line (default behavior)
        return;
      }
      // Enter without Shift: send message
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasContent = text.trim().length > 0;

  return (
    <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 pb-3 sm:pb-4 pt-2">
      <form
        onSubmit={handleSubmit}
        className="relative bg-white border border-[#dbd5c9] rounded-2xl shadow-xs focus-within:border-[#2d4d3a] focus-within:ring-1 focus-within:ring-[#2d4d3a]/30 transition-all flex items-end p-2 sm:p-2.5"
      >
        {/* Multiline textarea */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask RAG-MP about a medicinal plant..."
          disabled={isLoading}
          rows={1}
          className="flex-1 resize-none border-0 bg-transparent px-2 sm:px-3 py-1.5 text-sm sm:text-base text-[#1c2e23] placeholder-[#8f9f95] focus:outline-none focus:ring-0 max-h-36 disabled:opacity-50"
        />

        {/* Action button */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            type="submit"
            disabled={!hasContent || isLoading}
            className={`p-2 rounded-xl flex items-center justify-center transition-all ${
              hasContent && !isLoading
                ? 'bg-[#1c3829] hover:bg-[#13271c] text-[#f7f5f0] shadow-2xs hover:scale-105 active:scale-95 cursor-pointer'
                : 'bg-[#ede8df] text-[#a69e90] cursor-not-allowed opacity-70'
            }`}
            title={isLoading ? 'RAG-MP is thinking...' : 'Send message (Enter)'}
            aria-label="Send message"
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </form>

      {/* Subtle grounding note */}
      <div className="text-center mt-2">
        <p className="text-[11.5px] text-[#78887e]">
          RAG-MP generates grounded answers based on indexed botanical monographs.
        </p>
      </div>
    </div>
  );
}
