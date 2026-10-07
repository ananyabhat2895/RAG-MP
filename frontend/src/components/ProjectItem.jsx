import React, { useState, useRef, useEffect } from 'react';
import { MoreVertical, Edit2, Trash2, Check, X } from 'lucide-react';

export default function ProjectItem({ project, isActive, onSelect, onRename, onDelete, isLast }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(project.name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const menuRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const saveRename = () => {
    if (editName.trim()) onRename(project.id, editName.trim());
    else setEditName(project.name);
    setEditing(false); setMenuOpen(false);
  };

  const handleDeleteAttempt = () => {
    if (isLast) { setConfirmDelete(false); setMenuOpen(false); return; }
    onDelete(project.id);
    setMenuOpen(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1.5 px-1 py-1" onClick={e => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={editName}
          onChange={e => setEditName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') saveRename(); if (e.key === 'Escape') { setEditName(project.name); setEditing(false); } }}
          className="flex-1 bg-white border border-[#2d4d3a] rounded-lg px-2 py-1 text-xs text-[#1c2e22] focus:outline-none"
        />
        <button onClick={saveRename} className="p-1 rounded text-[#22442f] hover:bg-[#ddd6c7]"><Check className="w-3.5 h-3.5" /></button>
        <button onClick={() => { setEditName(project.name); setEditing(false); }} className="p-1 rounded text-rose-600 hover:bg-[#ddd6c7]"><X className="w-3.5 h-3.5" /></button>
      </div>
    );
  }

  return (
    <div className={`group relative rounded-xl flex items-center transition-all ${isActive ? 'bg-[#e4ddd0]' : 'hover:bg-[#eae3d5]'}`}>
      <button
        onClick={() => onSelect(project.id)}
        className={`flex-1 text-left px-2.5 py-2 text-xs sm:text-[13px] font-medium flex items-center gap-2 truncate focus:outline-none ${isActive ? 'text-[#14261b] font-semibold' : 'text-[#485c50] hover:text-[#172e21]'}`}
        title={project.description || project.name}
      >
        <span className="select-none">{project.icon || '📁'}</span>
        <span className="truncate">{project.name}</span>
        {isActive && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[#2d523b] flex-shrink-0" />}
      </button>

      {/* 3-dot menu */}
      <div ref={menuRef} className="relative flex-shrink-0 pr-1.5">
        <button
          onClick={e => { e.stopPropagation(); setMenuOpen(p => !p); setConfirmDelete(false); }}
          className={`p-1 rounded-lg text-[#667a6d] hover:text-[#183121] hover:bg-[#ded6c7] transition-colors ${menuOpen || isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
          aria-label="Project options"
        >
          <MoreVertical className="w-3.5 h-3.5" />
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-full mt-1 w-40 bg-white border border-[#ded8cb] rounded-xl shadow-lg z-50 py-1 text-xs" onClick={e => e.stopPropagation()}>
            {confirmDelete ? (
              <div className="p-2 space-y-1.5">
                {isLast
                  ? <p className="text-[11px] text-[#3d4f44]">Cannot delete the only project.</p>
                  : <p className="text-[11px] font-semibold text-rose-700">Delete "{project.name}"?</p>
                }
                <div className="flex gap-1.5">
                  {!isLast && (
                    <button onClick={handleDeleteAttempt} className="flex-1 py-1 px-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-[11px] font-medium transition-colors">Delete</button>
                  )}
                  <button onClick={() => setConfirmDelete(false)} className="py-1 px-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md text-[11px]">{isLast ? 'OK' : 'Cancel'}</button>
                </div>
              </div>
            ) : (
              <>
                <button onClick={() => { setEditing(true); setMenuOpen(false); }} className="w-full text-left px-3 py-1.5 text-[#2d4034] hover:bg-[#f2eee5] flex items-center gap-2">
                  <Edit2 className="w-3 h-3 text-[#586d60]" /><span>Rename</span>
                </button>
                <button onClick={() => setConfirmDelete(true)} className="w-full text-left px-3 py-1.5 text-rose-700 hover:bg-rose-50 flex items-center gap-2">
                  <Trash2 className="w-3 h-3 text-rose-600" /><span>Delete</span>
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
