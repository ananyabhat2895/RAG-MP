import React, { useState, useRef, useEffect } from 'react';
import { Menu, Plus } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import WelcomeScreen from '../components/WelcomeScreen';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import TypingIndicator from '../components/TypingIndicator';
import { useChat } from '../hooks/useChat';

export default function Chatbot() {
  const {
    filteredChats,
    activeChatId,
    activeChat,
    activeMessages,
    activeProject,
    projects,
    searchQuery,
    setSearchQuery,
    isLoading,
    startNewChat,
    selectChat,
    selectProject,
    addProject,
    renameProject,
    deleteProject,
    sendMessage,
    retryLastMessage,
    renameChat,
    deleteChat
  } = useChat();

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [autoFocusKey, setAutoFocusKey] = useState(0);
  const messagesEndRef = useRef(null);

  // Auto-scroll when messages update or loading state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeMessages, isLoading]);

  const handleStartNewChat = () => {
    startNewChat();
    setAutoFocusKey((prev) => prev + 1);
  };

  const handleSelectChat = (id) => {
    selectChat(id);
    setAutoFocusKey((prev) => prev + 1);
  };

  return (
    <div className="flex h-screen h-[100dvh] bg-[#fbf9f5] text-[#1e2a22] overflow-hidden">
      {/* Left Sidebar */}
      <Sidebar
        filteredChats={filteredChats}
        activeChatId={activeChatId}
        activeProject={activeProject}
        projects={projects}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onNewChat={handleStartNewChat}
        onSelectChat={handleSelectChat}
        onSelectProject={selectProject}
        onAddProject={addProject}
        onRenameProject={renameProject}
        onDeleteProject={deleteProject}
        onRenameChat={renameChat}
        onDeleteChat={deleteChat}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
        {/* Top Navbar Header */}
        <header className="h-14 bg-[#fbf9f5] border-b border-[#e2dcd0] px-4 flex items-center justify-between flex-shrink-0 z-10">
          <div className="flex items-center gap-2.5 truncate">
            {/* Mobile Hamburger Menu Toggle */}
            <button
              onClick={() => setIsSidebarOpen((prev) => !prev)}
              className="lg:hidden p-1.5 rounded-lg text-[#55695c] hover:text-[#162d20] hover:bg-[#eae3d5] transition-colors flex-shrink-0"
              aria-label="Toggle sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Title / Active Context */}
            <div className="flex items-center gap-2 truncate">
              <span className="font-serif font-bold text-base text-[#162d20] truncate">
                {activeChat ? activeChat.title : 'RAG-MP'}
              </span>
              <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium text-[#445b4c] bg-[#eee8db] border border-[#dfd8ca] px-2 py-0.5 rounded-md">
                <span>🌿</span>
                <span>Medicinal Plants</span>
              </span>
            </div>
          </div>

          {/* Quick New Chat Button */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleStartNewChat}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-[#1c3829] bg-[#ede6d8] hover:bg-[#e2dac9] transition-colors"
              title="Start a new chat"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New chat</span>
            </button>
          </div>
        </header>

        {/* Scrollable Chat Area */}
        <div className="flex-1 overflow-y-auto px-2 sm:px-4 py-4 min-w-0">
          {activeMessages.length === 0 ? (
            <WelcomeScreen
              onSelectPrompt={sendMessage}
              activeProject={activeProject}
            />
          ) : (
            <div className="space-y-4 pb-4">
              {activeMessages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onRetry={retryLastMessage}
                />
              ))}

              {isLoading && <TypingIndicator />}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Fixed Bottom Input */}
        <div className="flex-shrink-0 bg-[#fbf9f5] border-t border-[#e6e0d4]/80">
          <ChatInput
            onSendMessage={sendMessage}
            isLoading={isLoading}
            autoFocusKey={autoFocusKey}
          />
        </div>
      </main>
    </div>
  );
}
