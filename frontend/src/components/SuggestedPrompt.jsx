import React from 'react';

export default function SuggestedPrompt({ icon, prompt, onSelect }) {
  return (
    <button
      onClick={() => onSelect(prompt)}
      className="text-left p-3.5 sm:p-4 rounded-xl bg-white border border-[#e4ded3] hover:border-[#2d4d3a] hover:bg-[#f6f2e8] transition-all duration-150 shadow-2xs flex items-start gap-3 group focus:outline-none focus:ring-1 focus:ring-[#2d4d3a]"
    >
      <span className="text-base sm:text-lg select-none flex-shrink-0 mt-0.5">{icon}</span>
      <div className="flex-1">
        <span className="text-xs sm:text-sm font-medium text-[#223528] group-hover:text-[#14261b] leading-snug">
          "{prompt}"
        </span>
      </div>
    </button>
  );
}
