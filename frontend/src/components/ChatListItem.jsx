import React, { useState, useRef, useEffect } from 'react';
import { MoreVertical, Edit2, Trash2, Check, X, MessageSquare } from 'lucide-react';

export default function ChatListItem({
  chat,
  isActive,
  onSelect,
  onRename,
  onDelete
}) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(chat.title);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

  const menuRef = useRef(null);
  const inputRef = useRef(null);

  // Close dropdown menu if clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsMenuOpen(false);
      }
    }
    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  // Focus rename input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSaveRename = (e) => {
    if (e) e.stopPropagation();
    if (editTitle.trim()) {
      onRename(chat.id, editTitle.trim());
    } else {
      setEditTitle(chat.title);
    }
    setIsEditing(false);
    setIsMenuOpen(false);
  };

  const handleCancelRename = (e) => {
    if (e) e.stopPropagation();
    setEditTitle(chat.title);
    setIsEditing(false);
    setIsMenuOpen(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSaveRename(e);
    } else if (e.key === 'Escape') {
      handleCancelRename(e);
    }
  };

  const handleConfirmDelete = (e) => {
    e.stopPropagation();
    onDelete(chat.id);
    setIsConfirmingDelete(false);
    setIsMenuOpen(false);
  };

  return (
    <div
      className={`group relative rounded-xl transition-all ${
        isActive
          ? 'bg-[#e4ddd0] text-[#14261b] font-medium'
          : 'text-[#384c3f] hover:bg-[#eae3d5] hover:text-[#14261b]'
      }`}
    >
      {/* RENAME MODE */}
      {isEditing ? (
        <div className="flex items-center gap-1.5 p-1.5" onClick={(e) => e.stopPropagation()}>
          <input
            ref={inputRef}
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-white border border-[#2d4d3a] rounded-lg px-2 py-1 text-xs text-[#1c2e22] focus:outline-none"
          />
          <button
            onClick={handleSaveRename}
            className="p-1 rounded-md text-[#22442f] hover:bg-[#dad2c3]"
            title="Save"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleCancelRename}
            className="p-1 rounded-md text-[#783630] hover:bg-[#dad2c3]"
            title="Cancel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        /* STANDARD ROW */
        <div className="flex items-center justify-between w-full">
          <button
            onClick={() => onSelect(chat.id)}
            className="flex-1 text-left px-2.5 py-2 text-xs sm:text-[13px] flex items-center gap-2 truncate focus:outline-none"
            title={chat.title}
          >
            <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-[#697f71]" />
            <span className="truncate">{chat.title}</span>
          </button>

          {/* 3-Dot Menu Button */}
          <div className="relative flex-shrink-0 pr-1.5" ref={menuRef}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsMenuOpen((prev) => !prev);
                setIsConfirmingDelete(false);
              }}
              className={`p-1 rounded-lg text-[#667a6d] hover:text-[#183121] hover:bg-[#ded6c7] transition-colors ${
                isMenuOpen || isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
              }`}
              title="Chat actions"
              aria-label="Chat options"
            >
              <MoreVertical className="w-3.5 h-3.5" />
            </button>

            {/* Dropdown Menu */}
            {isMenuOpen && (
              <div
                className="absolute right-0 top-full mt-1 w-36 bg-white border border-[#ded8cb] rounded-xl shadow-lg z-50 py-1 text-xs"
                onClick={(e) => e.stopPropagation()}
              >
                {isConfirmingDelete ? (
                  <div className="p-2 space-y-1.5">
                    <p className="text-[11px] font-semibold text-rose-700">Delete chat?</p>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={handleConfirmDelete}
                        className="flex-1 py-1 px-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-[11px] font-medium transition-colors"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => setIsConfirmingDelete(false)}
                        className="py-1 px-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md text-[11px]"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        setIsEditing(true);
                        setIsMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-1.5 text-[#2d4034] hover:bg-[#f2eee5] flex items-center gap-2"
                    >
                      <Edit2 className="w-3 h-3 text-[#586d60]" />
                      <span>Rename</span>
                    </button>
                    <button
                      onClick={() => setIsConfirmingDelete(true)}
                      className="w-full text-left px-3 py-1.5 text-rose-700 hover:bg-rose-50 flex items-center gap-2"
                    >
                      <Trash2 className="w-3 h-3 text-rose-600" />
                      <span>Delete</span>
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
