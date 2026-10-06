import React from 'react';
import SuggestedPrompt from './SuggestedPrompt';

export default function WelcomeScreen({ onSelectPrompt, activeProject = 'medicinal-plants' }) {
  const suggestedPrompts = [
    {
      icon: '🌿',
      prompt: 'Tell me about Ashwagandha'
    },
    {
      icon: '🔬',
      prompt: 'What is the botanical name of Tulsi?'
    },
    {
      icon: '🌱',
      prompt: 'Compare Neem and Turmeric'
    },
    {
      icon: '📚',
      prompt: 'What medicinal plants are used in Ayurveda?'
    }
  ];

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 sm:py-14 flex flex-col items-center text-center">
      {/* Botanical emblem */}
      <div className="w-13 h-13 rounded-2xl bg-[#ebe4d5] border border-[#dcd4c3] flex items-center justify-center text-[#1c3829] mb-5 shadow-2xs">
        <svg
          className="w-7 h-7 text-[#1c3829]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
          <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
        </svg>
      </div>

      {/* Heading */}
      <div className="space-y-1 mb-2">
        <h1 className="text-2xl sm:text-3xl font-serif font-bold text-[#162d20] tracking-tight">
          Welcome to RAG-MP 🌿
        </h1>
        <p className="text-base sm:text-lg text-[#3b5344] font-medium">
          Ask me anything about medicinal plants.
        </p>
      </div>

      <p className="text-xs sm:text-sm text-[#5d7164] max-w-md mb-8 leading-relaxed">
        Grounded in verified botanical taxonomy, phytochemical literature, and traditional Ayurvedic monographs.
      </p>

      {/* Suggested Prompts Section */}
      <div className="w-full text-left space-y-2.5">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#6a7c70]">
            Suggested questions
          </span>
          <span className="text-[11px] text-[#4d6355] bg-[#ece6d9] px-2 py-0.5 rounded-md font-medium border border-[#ded7c8]">
            🌿 {activeProject === 'medicinal-plants' ? 'Medicinal Plants' : activeProject}
          </span>
        </div>

        <div className="grid sm:grid-cols-2 gap-2.5">
          {suggestedPrompts.map((item, idx) => (
            <SuggestedPrompt
              key={idx}
              icon={item.icon}
              prompt={item.prompt}
              onSelect={onSelectPrompt}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
