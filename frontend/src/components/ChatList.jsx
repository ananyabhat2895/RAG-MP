import React from 'react';
import ChatListItem from './ChatListItem';

export default function ChatList({
  chats = [],
  activeChatId,
  searchQuery,
  onSelectChat,
  onRenameChat,
  onDeleteChat
}) {
  if (chats.length === 0) {
    return (
      <div className="py-4 px-2 text-center text-xs text-[#7d9084]">
        {searchQuery ? (
          <p>No conversations found for "{searchQuery}"</p>
        ) : (
          <p>No recent conversations yet. Ask a question to begin!</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      {chats.map((chat) => (
        <ChatListItem
          key={chat.id}
          chat={chat}
          isActive={chat.id === activeChatId}
          onSelect={onSelectChat}
          onRename={onRenameChat}
          onDelete={onDeleteChat}
        />
      ))}
    </div>
  );
}
