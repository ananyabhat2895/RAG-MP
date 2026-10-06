/**
 * LocalStorage Persistence Layer for RAG-MP Conversations
 * 
 * Manages chat sessions, active state, projects, and title generation.
 */

const STORAGE_KEY_CHATS = 'rag_mp_conversations_v1';
const STORAGE_KEY_ACTIVE_CHAT = 'rag_mp_active_chat_id';
const STORAGE_KEY_ACTIVE_PROJECT = 'rag_mp_active_project';
const STORAGE_KEY_PROJECTS = 'rag_mp_projects_v1';

export const DEFAULT_PROJECT = {
  id: 'medicinal-plants',
  name: 'Medicinal Plants',
  icon: '🌿',
  description: 'Botanical taxonomy, vernacular names, and Ayurvedic monographs'
};

/** Load projects list, always including the default. */
export function getSavedProjects() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PROJECTS);
    const parsed = raw ? JSON.parse(raw) : [];
    const list = Array.isArray(parsed) ? parsed : [];
    // Ensure default is always present
    if (!list.find(p => p.id === DEFAULT_PROJECT.id)) {
      return [DEFAULT_PROJECT, ...list];
    }
    return list;
  } catch {
    return [DEFAULT_PROJECT];
  }
}

/** Persist projects list to localStorage. */
export function saveProjects(projects) {
  try {
    localStorage.setItem(STORAGE_KEY_PROJECTS, JSON.stringify(projects));
  } catch (err) {
    console.error('Failed to save projects:', err);
  }
}

/** Generate a project id from name. */
export function createProject({ name, description = '', icon = '📁' }) {
  const id = `proj_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
  return { id, name: name.trim(), description: description.trim(), icon };
}

/**
 * Loads all saved conversations from localStorage.
 * @returns {Array<Object>}
 */
export function getSavedChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_CHATS);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    console.error('Failed to parse chats from localStorage:', err);
    return [];
  }
}

/**
 * Saves all conversations to localStorage.
 * @param {Array<Object>} chats
 */
export function saveAllChats(chats) {
  try {
    localStorage.setItem(STORAGE_KEY_CHATS, JSON.stringify(chats));
  } catch (err) {
    console.error('Failed to save chats to localStorage:', err);
  }
}

/**
 * Retrieves the currently active conversation ID.
 * @returns {string|null}
 */
export function getStoredActiveChatId() {
  try {
    return localStorage.getItem(STORAGE_KEY_ACTIVE_CHAT);
  } catch {
    return null;
  }
}

/**
 * Stores the active conversation ID.
 * @param {string|null} chatId
 */
export function setStoredActiveChatId(chatId) {
  try {
    if (chatId) {
      localStorage.setItem(STORAGE_KEY_ACTIVE_CHAT, chatId);
    } else {
      localStorage.removeItem(STORAGE_KEY_ACTIVE_CHAT);
    }
  } catch (err) {
    console.error('Failed to set active chat ID in localStorage:', err);
  }
}

/**
 * Retrieves the currently active project ID.
 * @returns {string}
 */
export function getStoredActiveProject() {
  try {
    return localStorage.getItem(STORAGE_KEY_ACTIVE_PROJECT) || DEFAULT_PROJECT.id;
  } catch {
    return DEFAULT_PROJECT.id;
  }
}

/**
 * Stores the active project ID.
 * @param {string} projectId
 */
export function setStoredActiveProject(projectId) {
  try {
    localStorage.setItem(STORAGE_KEY_ACTIVE_PROJECT, projectId);
  } catch (err) {
    console.error('Failed to set active project in localStorage:', err);
  }
}

/**
 * Creates a brand new conversation object.
 * @param {Object} options
 * @returns {Object}
 */
export function createNewChat({
  project = DEFAULT_PROJECT.id,
  title = 'New Conversation',
  messages = []
} = {}) {
  const timestamp = Date.now();
  const randomSuffix = Math.random().toString(36).substring(2, 8);
  return {
    id: `chat_${timestamp}_${randomSuffix}`,
    title,
    messages,
    project,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
}

/**
 * Generates a concise, meaningful title from the user's first query.
 * @param {string} query
 * @returns {string}
 */
export function generateChatTitle(query) {
  if (!query || typeof query !== 'string') return 'New Conversation';

  const clean = query.trim().replace(/[?!.,;:]+$/, '');
  const lower = clean.toLowerCase();

  // Botanical common query patterns
  if (lower.includes('ashwagandha')) {
    if (lower.includes('benefit') || lower.includes('use')) return 'Ashwagandha Benefits';
    return 'Ashwagandha Information';
  }
  if (lower.includes('tulsi') && (lower.includes('neem') || lower.includes('compare'))) {
    return 'Tulsi vs Neem';
  }
  if (lower.includes('neem') && lower.includes('turmeric')) {
    return 'Neem & Turmeric Comparison';
  }
  if (lower.includes('botanical name of tulsi') || (lower.includes('tulsi') && lower.includes('botanical'))) {
    return 'Tulsi Botanical Name';
  }
  if (lower.includes('tulsi')) {
    if (lower.includes('use')) return 'Tulsi Medicinal Uses';
    return 'Tulsi Overview';
  }
  if (lower.includes('ayurveda') || lower.includes('ayurvedic')) {
    return 'Ayurvedic Medicinal Plants';
  }
  if (lower.includes('neem')) {
    if (lower.includes('use')) return 'Neem Medicinal Uses';
    return 'Neem Properties';
  }
  if (lower.includes('turmeric') || lower.includes('haldi')) {
    return 'Turmeric & Curcumin';
  }
  if (lower.includes('giloy') || lower.includes('guduchi')) {
    return 'Giloy Medicinal Uses';
  }
  if (lower.includes('brahmi')) {
    return 'Brahmi Cognitive Herb';
  }
  if (lower.includes('shatavari')) {
    return 'Shatavari Overview';
  }

  // Strip conversational leading filler phrases
  let trimmed = clean
    .replace(/^(what is the|what are the|tell me about|can you tell me about|explain|describe|show me|how to use)\s+/i, '')
    .trim();

  if (trimmed.length > 0) {
    // Capitalize words
    const words = trimmed.split(/\s+/).slice(0, 4);
    const capitalized = words
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
    return capitalized.length > 32 ? `${capitalized.slice(0, 29)}...` : capitalized;
  }

  return clean.slice(0, 30);
}
