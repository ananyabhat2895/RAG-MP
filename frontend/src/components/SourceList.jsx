import React from 'react';
import { BookOpen } from 'lucide-react';

export default function SourceList({ sources = [] }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-4 pt-3 border-t border-[#e2dcd2] text-xs text-[#526a5c]">
      <div className="font-semibold text-[#1c3829] mb-1.5 flex items-center gap-1.5">
        <BookOpen className="w-3.5 h-3.5 text-[#2d523b]" />
        <span>Sources:</span>
      </div>
      <ul className="space-y-1 pl-1">
        {sources.map((src, index) => {
          const sourceText = typeof src === 'string' ? src : (src.title || src.name || JSON.stringify(src));
          return (
            <li key={index} className="flex items-start gap-1.5 text-[#465b4f] leading-snug">
              <span className="text-[#8aa293] select-none font-medium">•</span>
              <span>{sourceText}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
