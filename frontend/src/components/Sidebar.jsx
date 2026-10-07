import React, { useState } from 'react';
import { Plus, Search, X, FolderKanban } from 'lucide-react';
import ProjectItem from './ProjectItem';
import ChatList from './ChatList';
import AddProjectModal from './AddProjectModal';

export default function Sidebar({
  filteredChats = [],
  activeChatId,
  activeProject,
  projects = [],
  searchQuery,
  onSearchChange,
  onNewChat,
  onSelectChat,
  onSelectProject,
  onAddProject,
  onRenameProject,
  onDeleteProject,
  onRenameChat,
  onDeleteChat,
  isOpen,
  onClose
}) {
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <>
      {/* Mobile Drawer Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-[#14261b]/35 backdrop-blur-2xs z-40 lg:hidden transition-opacity"
          aria-hidden="true"
        />
      )}

      {/* Add Project Modal */}
      {showAddModal && (
        <AddProjectModal
          onClose={() => setShowAddModal(false)}
          onConfirm={(data) => {
            onAddProject(data);
            setShowAddModal(false);
          }}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed lg:static top-0 bottom-0 left-0 z-50 w-72 md:w-68 lg:w-68 bg-[#f5efe3] border-r border-[#e2dcd0] flex flex-col transition-transform duration-200 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Top Header */}
        <div className="p-4 pb-3 border-b border-[#e2dcd0] flex items-start justify-between">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-[#1c3829] text-[#e8f0ec] flex items-center justify-center text-xs shadow-2xs">
                🌿
              </div>
              <h2 className="font-serif font-bold text-lg text-[#162d20] tracking-tight leading-none">
                RAG-MP
              </h2>
            </div>
            <p className="text-[11.5px] text-[#55695c] font-normal leading-tight pt-1">
              Medicinal Plant Knowledge Assistant
            </p>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-lg text-[#667a6d] hover:text-[#162d20] hover:bg-[#eae3d5] transition-colors"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* New Chat + Search */}
        <div className="p-3 pb-2 space-y-2">
          <button
            onClick={() => { onNewChat(); if (onClose) onClose(); }}
            className="w-full flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl bg-[#1c3829] hover:bg-[#13271c] text-[#f7f5f0] text-xs sm:text-sm font-semibold transition-all shadow-2xs active:scale-[0.98] cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>

          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#7d9084] pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search Chats"
              className="w-full pl-8 pr-7 py-1.5 text-xs bg-white border border-[#dbd4c7] rounded-lg text-[#1c2e22] placeholder-[#8d9e93] focus:outline-none focus:border-[#2d4d3a] focus:ring-1 focus:ring-[#2d4d3a]/25 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => onSearchChange('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#7d9084] hover:text-[#1c2e22] p-0.5"
                title="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Scrollable Center */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4">
          {/* Projects Section */}
          <div className="space-y-1">
            {/* Section Header with + Add Project */}
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#697d70]">
                <FolderKanban className="w-3 h-3" />
                <span>Projects</span>
              </div>
              <button
                onClick={() => setShowAddModal(true)}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10.5px] font-medium text-[#4d6755] hover:text-[#162d20] hover:bg-[#e4ddd0] transition-colors"
                title="Add a new project"
              >
                <Plus className="w-3 h-3" />
                <span>Add Project</span>
              </button>
            </div>

            {/* Project List */}
            <div className="space-y-0.5">
              {projects.map((project) => (
                <ProjectItem
                  key={project.id}
                  project={project}
                  isActive={activeProject === project.id}
                  isLast={projects.length === 1}
                  onSelect={(pId) => { onSelectProject(pId); if (onClose) onClose(); }}
                  onRename={onRenameProject}
                  onDelete={onDeleteProject}
                />
              ))}
            </div>
          </div>

          {/* Recent Chats Section */}
          <div className="space-y-1 pt-2 border-t border-[#e2dcd0]">
            <div className="flex items-center justify-between px-2 text-[11px] font-bold uppercase tracking-wider text-[#697d70]">
              <span>Recent Chats</span>
              {filteredChats.length > 0 && (
                <span className="text-[10px] text-[#86998c] font-normal">{filteredChats.length}</span>
              )}
            </div>

            <ChatList
              chats={filteredChats}
              activeChatId={activeChatId}
              searchQuery={searchQuery}
              onSelectChat={(id) => { onSelectChat(id); if (onClose) onClose(); }}
              onRenameChat={onRenameChat}
              onDeleteChat={onDeleteChat}
            />
          </div>
        </div>

        {/* Bottom Footer */}
        <div className="p-3 border-t border-[#e2dcd0] bg-[#efe9dd] flex items-center justify-between text-[11px] text-[#697d70]">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2d523b]" />
            <span>RAG-MP v1.0 • Botanical AI</span>
          </span>
          <span className="text-[10px] text-[#84968a]">Offline Index</span>
        </div>
      </aside>
    </>
  );
}
