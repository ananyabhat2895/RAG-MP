import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  getSavedChats,
  saveAllChats,
  getStoredActiveChatId,
  setStoredActiveChatId,
  getStoredActiveProject,
  setStoredActiveProject,
  getSavedProjects,
  saveProjects,
  createProject,
  createNewChat,
  generateChatTitle,
  DEFAULT_PROJECT
} from '../utils/chatStorage';
import { sendMessage as sendBotanicalMessage } from '../services/chatService';

export function useChat() {
  const [chats, setChats] = useState(() => getSavedChats());
  const [activeChatId, setActiveChatIdState] = useState(() => getStoredActiveChatId());
  const [activeProject, setActiveProjectState] = useState(() => getStoredActiveProject());
  const [projects, setProjectsState] = useState(() => getSavedProjects());
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Sync activeChatId to localStorage
  const setActiveChatId = useCallback((id) => {
    setActiveChatIdState(id);
    setStoredActiveChatId(id);
  }, []);

  // Sync activeProject to localStorage
  const selectProject = useCallback((projectId) => {
    setActiveProjectState(projectId);
    setStoredActiveProject(projectId);
  }, []);

  // Persist projects whenever they change
  useEffect(() => { saveProjects(projects); }, [projects]);

  const addProject = useCallback(({ name, description, icon }) => {
    const np = createProject({ name, description, icon });
    setProjectsState(prev => { const next = [...prev, np]; return next; });
    setActiveProjectState(np.id);
    setStoredActiveProject(np.id);
  }, []);

  const renameProject = useCallback((id, newName) => {
    if (!newName.trim()) return;
    setProjectsState(prev => prev.map(p => p.id === id ? { ...p, name: newName.trim() } : p));
  }, []);

  const deleteProject = useCallback((id) => {
    setProjectsState(prev => {
      const remaining = prev.filter(p => p.id !== id);
      return remaining;
    });
    setActiveProjectState(prev => {
      if (prev === id) {
        const first = projects.find(p => p.id !== id);
        const next = first ? first.id : DEFAULT_PROJECT.id;
        setStoredActiveProject(next);
        return next;
      }
      return prev;
    });
  }, [projects]);

  // Keep localStorage updated whenever chats list changes
  useEffect(() => {
    saveAllChats(chats);
  }, [chats]);

  // Determine active conversation
  const activeChat = useMemo(() => {
    if (!activeChatId) return null;
    return chats.find((c) => c.id === activeChatId) || null;
  }, [chats, activeChatId]);

  const activeMessages = useMemo(() => {
    return activeChat ? activeChat.messages : [];
  }, [activeChat]);

  // Start a fresh new chat
  const startNewChat = useCallback(() => {
    setActiveChatId(null);
    setSearchQuery('');
  }, [setActiveChatId]);

  // Select an existing conversation
  const selectChat = useCallback((id) => {
    setActiveChatId(id);
  }, [setActiveChatId]);

  // Send a message
  const handleSendMessage = useCallback(async (userText) => {
    if (!userText || !userText.trim() || isLoading) return;

    const trimmedText = userText.trim();
    const nowIso = new Date().toISOString();

    let targetChatId = activeChatId;
    let currentChat = chats.find((c) => c.id === targetChatId);

    // If no chat is active, create a new one with a dynamic title from the first question
    if (!currentChat) {
      const generatedTitle = generateChatTitle(trimmedText);
      const newChat = createNewChat({
        project: activeProject || DEFAULT_PROJECT.id,
        title: generatedTitle,
        messages: []
      });
      targetChatId = newChat.id;
      currentChat = newChat;

      // Update state and storage with new chat
      setChats((prev) => [newChat, ...prev]);
      setActiveChatId(newChat.id);
    } else if (currentChat.messages.length === 0) {
      // First message in an existing empty conversation -> update title
      const newTitle = generateChatTitle(trimmedText);
      setChats((prev) =>
        prev.map((c) => (c.id === currentChat.id ? { ...c, title: newTitle } : c))
      );
    }

    const userMessage = {
      id: `msg_user_${Date.now()}`,
      sender: 'user',
      text: trimmedText,
      timestamp: nowIso
    };

    // Prepare previous history for the RAG service
    const existingMessages = currentChat ? currentChat.messages : [];
    const conversationHistory = existingMessages
      .filter((m) => !m.isError)
      .map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
      }));

    // Optimistically update conversation with user message
    const updatedMessagesWithUser = [...existingMessages, userMessage];

    setChats((prev) =>
      prev.map((c) =>
        c.id === targetChatId
          ? { ...c, messages: updatedMessagesWithUser, updatedAt: nowIso }
          : c
      )
    );

    setIsLoading(true);

    try {
      const response = await sendBotanicalMessage(
        trimmedText,
        conversationHistory,
        activeProject || DEFAULT_PROJECT.id
      );

      const assistantMessage = {
        id: `msg_asst_${Date.now() + 1}`,
        sender: 'assistant',
        text: response.answer || response.text || '',
        sources: Array.isArray(response.sources) ? response.sources : [],
        timestamp: new Date().toISOString()
      };

      setChats((prev) =>
        prev.map((c) =>
          c.id === targetChatId
            ? {
                ...c,
                messages: [...updatedMessagesWithUser, assistantMessage],
                updatedAt: new Date().toISOString()
              }
            : c
        )
      );
    } catch (err) {
      console.error('Error querying botanical knowledge base:', err);

      const errorMessage = {
        id: `msg_err_${Date.now() + 1}`,
        sender: 'assistant',
        isError: true,
        text: 'Something went wrong while processing your question. Please try again.',
        sources: [],
        timestamp: new Date().toISOString()
      };

      setChats((prev) =>
        prev.map((c) =>
          c.id === targetChatId
            ? {
                ...c,
                messages: [...updatedMessagesWithUser, errorMessage],
                updatedAt: new Date().toISOString()
              }
            : c
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [activeChatId, chats, activeProject, isLoading, setActiveChatId]);

  // Retry the last message in case of failure
  const handleRetry = useCallback(() => {
    if (!activeChat || activeMessages.length === 0 || isLoading) return;

    // Find the last user message
    const lastUserMessage = [...activeMessages]
      .reverse()
      .find((m) => m.sender === 'user');

    if (!lastUserMessage) return;

    // Remove the trailing error message if present
    const cleanedMessages = activeMessages.filter((m) => !m.isError);

    setChats((prev) =>
      prev.map((c) =>
        c.id === activeChat.id ? { ...c, messages: cleanedMessages } : c
      )
    );

    // Resend the last user message
    handleSendMessage(lastUserMessage.text);
  }, [activeChat, activeMessages, isLoading, handleSendMessage]);

  // Rename a conversation
  const handleRenameChat = useCallback((id, newTitle) => {
    if (!newTitle || !newTitle.trim()) return;
    const cleanTitle = newTitle.trim();
    setChats((prev) =>
      prev.map((c) =>
        c.id === id
          ? { ...c, title: cleanTitle, updatedAt: new Date().toISOString() }
          : c
      )
    );
  }, []);

  // Delete a conversation
  const handleDeleteChat = useCallback((id) => {
    setChats((prev) => {
      const remaining = prev.filter((c) => c.id !== id);
      return remaining;
    });

    // If the active chat was deleted, reset active chat
    if (activeChatId === id) {
      setActiveChatId(null);
    }
  }, [activeChatId, setActiveChatId]);

  // Filter chats by search query across both title and message content
  const filteredChats = useMemo(() => {
    if (!searchQuery.trim()) return chats;
    const query = searchQuery.toLowerCase().trim();

    return chats.filter((c) => {
      const titleMatches = c.title && c.title.toLowerCase().includes(query);
      const contentMatches = c.messages && c.messages.some(
        (m) => m.text && m.text.toLowerCase().includes(query)
      );
      return titleMatches || contentMatches;
    });
  }, [chats, searchQuery]);

  return {
    chats,
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
    sendMessage: handleSendMessage,
    retryLastMessage: handleRetry,
    renameChat: handleRenameChat,
    deleteChat: handleDeleteChat
  };
}
