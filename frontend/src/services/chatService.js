const BACKEND_URL = import.meta.env.VITE_RAG_API_URL || '/api/rag-query';

export async function sendMessage(query) {
  if (!query || typeof query !== 'string' || !query.trim()) {
    throw new Error('Query must be a non-empty string.');
  }

  let response;
  try {
    response = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: query.trim() })
    });
  } catch {
    throw new Error('Could not connect to the RAG API. Make sure the Python backend is running.');
  }

  const responseText = await response.text();
  let data;
  try {
    data = responseText ? JSON.parse(responseText) : {};
  } catch {
    throw new Error(`The RAG API returned an invalid response (HTTP ${response.status}).`);
  }

  if (!response.ok || data.success === false) {
    const detail = data.detail || data.error;
    const message = typeof detail === 'string' ? detail : '';
    throw new Error(message || `RAG API request failed (HTTP ${response.status}).`);
  }

  if (typeof data.answer !== 'string' || !data.answer.trim()) {
    throw new Error('The RAG API returned an empty answer. Please try again.');
  }

  return {
    answer: data.answer.trim(),
    sources: Array.isArray(data.sources)
      ? data.sources.filter(source => typeof source === 'string' && source.trim())
      : []
  };
}
