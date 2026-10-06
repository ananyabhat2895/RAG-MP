import React, { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';

const ICONS = ['📁', '🌿', '📚', '🔬', '🌱', '💊', '🏥', '🧪', '🌸', '🍃'];

export default function AddProjectModal({ onClose, onConfirm }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [icon, setIcon] = useState('📁');
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) { setError('Project name is required.'); return; }
    onConfirm({ name: name.trim(), description: description.trim(), icon });
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-[#14261b]/40 backdrop-blur-sm px-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl border border-[#e0d9ce] w-full max-w-sm p-5 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#162d20]">Create a project</h2>
          <button onClick={onClose} className="p-1 rounded-lg text-[#7d9084] hover:bg-[#f0ebe0] hover:text-[#162d20] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* Icon picker */}
          <div className="flex flex-wrap gap-1.5">
            {ICONS.map(ic => (
              <button
                key={ic}
                type="button"
                onClick={() => setIcon(ic)}
                className={`w-8 h-8 rounded-lg text-base flex items-center justify-center transition-all ${icon === ic ? 'bg-[#1c3829] ring-1 ring-[#1c3829]' : 'bg-[#f2ede3] hover:bg-[#e6dfd0]'}`}
              >
                {ic}
              </button>
            ))}
          </div>

          {/* Name */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[#2d4034]">Project name</label>
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setError(''); }}
              placeholder="e.g. Ayurveda Research"
              className="w-full px-3 py-2 text-sm border border-[#dbd5c9] rounded-xl focus:outline-none focus:border-[#2d4d3a] focus:ring-1 focus:ring-[#2d4d3a]/30 text-[#1c2e22] placeholder-[#9aaa9f] transition-all"
            />
            {error && <p className="text-[11px] text-rose-600">{error}</p>}
          </div>

          {/* Description */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[#2d4034]">Description <span className="text-[#8a9e90] font-normal">(optional)</span></label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this project about?"
              className="w-full px-3 py-2 text-sm border border-[#dbd5c9] rounded-xl focus:outline-none focus:border-[#2d4d3a] focus:ring-1 focus:ring-[#2d4d3a]/30 text-[#1c2e22] placeholder-[#9aaa9f] transition-all"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-xl text-xs font-medium text-[#3d5244] bg-[#eee8db] hover:bg-[#e3dccf] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#1c3829] hover:bg-[#13271c] text-[#f7f5f0] transition-all shadow-2xs"
            >
              Create Project
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
