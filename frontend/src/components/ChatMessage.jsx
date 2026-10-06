import React, { useState } from 'react';
import { Copy, Check, RotateCcw, AlertCircle } from 'lucide-react';
import SourceList from './SourceList';

/**
 * Parses basic inline markdown formatting like **bold** and *italic*.
 */
function formatInlineText(text) {
  if (!text) return text;
  const parts = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={match.index} className="font-semibold text-[#14261b]">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={match.index} className="italic text-[#1d3325]">
          {token.slice(1, -1)}
        </em>
      );
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

export default function ChatMessage({ message, onRetry }) {
  const isUser = message.sender === 'user';
  const isError = Boolean(message.isError);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!message.text) return;
    navigator.clipboard.writeText(message.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Split into paragraphs / blocks
  const paragraphs = message.text ? message.text.split('\n\n') : [];

  return (
    <div className={`my-4 max-w-3xl mx-auto px-2 sm:px-4 ${isUser ? 'flex justify-end' : 'flex justify-start'}`}>
      {isUser ? (
        /* USER MESSAGE */
        <div className="max-w-[85%] sm:max-w-[75%] bg-[#1c3829] text-[#f7f5f0] px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm sm:text-[15px] leading-relaxed shadow-xs">
          <p className="whitespace-pre-wrap">{message.text}</p>
        </div>
      ) : (
        /* ASSISTANT MESSAGE */
        <div className="flex items-start gap-3 w-full">
          {/* Botanical Avatar or Error Indicator */}
          <div
            className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5 shadow-xs ${
              isError ? 'bg-[#7a322c] text-[#fbeeee]' : 'bg-[#1c3829] text-[#e8f0ec]'
            }`}
          >
            {isError ? (
              <AlertCircle className="w-3.5 h-3.5" />
            ) : (
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
            )}
          </div>

          <div className="flex-1 space-y-2 pt-0.5 max-w-2xl">
            {/* Header with Title and Actions */}
            <div className="flex items-center justify-between text-xs text-[#6e8074]">
              <span className={`font-semibold ${isError ? 'text-[#873229]' : 'text-[#1c3829]'}`}>
                {isError ? 'Notice' : 'RAG-MP Assistant'}
              </span>

              {!isError && (
                <button
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1 hover:text-[#1c3829] transition-colors px-1.5 py-0.5 rounded hover:bg-[#eae5db]"
                  title="Copy response to clipboard"
                  aria-label="Copy response"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-[#2d523b]" />
                      <span className="text-[11px] text-[#2d523b] font-medium">Copied ✓</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span className="text-[11px]">Copy</span>
                    </>
                  )}
                </button>
              )}
            </div>

            {/* Content Body */}
            {isError ? (
              <div className="bg-[#faebea] border border-[#eed2cf] rounded-xl p-3.5 space-y-2.5">
                <p className="text-sm text-[#7d3229] leading-relaxed">
                  {message.text || 'Something went wrong while processing your question. Please try again.'}
                </p>
                {onRetry && (
                  <button
                    onClick={onRetry}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-lg bg-[#7d3229] hover:bg-[#66271f] text-[#ffffff] transition-all shadow-2xs"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Retry</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="text-[14.5px] sm:text-[15.5px] text-[#223528] leading-[1.68] space-y-3 font-normal">
                {paragraphs.map((para, idx) => {
                  const lines = para.split('\n');
                  return (
                    <div key={idx} className="space-y-1">
                      {lines.map((line, lIdx) => {
                        const trimmedLine = line.trim();
                        // Check if bullet point
                        if (trimmedLine.startsWith('•') || trimmedLine.startsWith('-')) {
                          const content = trimmedLine.replace(/^[•-]\s*/, '');
                          return (
                            <div key={lIdx} className="flex items-start gap-2 pl-2">
                              <span className="text-[#32523f] select-none leading-relaxed">•</span>
                              <span className="flex-1 leading-relaxed">
                                {formatInlineText(content)}
                              </span>
                            </div>
                          );
                        }
                        // Check if numbered list (e.g., "1. ")
                        const numMatch = trimmedLine.match(/^(\d+)\.\s+(.*)$/);
                        if (numMatch) {
                          return (
                            <div key={lIdx} className="flex items-start gap-2 pl-2">
                              <span className="font-semibold text-[#1c3829] select-none text-xs mt-0.5">
                                {numMatch[1]}.
                              </span>
                              <span className="flex-1 leading-relaxed">
                                {formatInlineText(numMatch[2])}
                              </span>
                            </div>
                          );
                        }
                        // Standard paragraph line
                        return (
                          <p key={lIdx} className="whitespace-pre-wrap leading-relaxed">
                            {formatInlineText(line)}
                          </p>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Source citations */}
            {!isError && <SourceList sources={message.sources} />}
          </div>
        </div>
      )}
    </div>
  );
}
