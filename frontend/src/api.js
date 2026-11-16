
/**
 * API client for the LLM Council backend.
 */

const API_BASE = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

async function handleResponse(response, defaultError) {
  if (!response.ok) {
    let details = '';

    try {
      details = await response.text();
    } catch {
      // Ignore response parsing errors.
    }

    throw new Error(
      `${defaultError} (${response.status})${details ? ': ' + details : ''}`
    );
  }

  return response;
}

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(
      `${API_BASE}/api/conversations`
    );

    await handleResponse(response, 'Failed to list conversations');

    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(
      `${API_BASE}/api/conversations`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      }
    );

    await handleResponse(response, 'Failed to create conversation');

    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );

    await handleResponse(response, 'Failed to get conversation');

    return response.json();
  },

  /**
   * Send a normal, non-streaming message.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    await handleResponse(response, 'Failed to send message');

    return response.json();
  },

  /**
   * Send a message and receive Server-Sent Events.
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ content }),
      }
    );

    await handleResponse(response, 'Failed to send streaming message');

    if (!response.body) {
      throw new Error('Streaming response body is unavailable');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = '';

    const processEvent = (eventBlock) => {
      const lines = eventBlock.split(/\r?\n/);

      const dataLines = lines
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart());

      if (dataLines.length === 0) return;

      const data = dataLines.join('\n');

      if (!data || data === '[DONE]') return;

      try {
        const event = JSON.parse(data);

        if (event.type) {
          onEvent(event.type, event);
        } else {
          console.warn('SSE event has no type:', event);
        }
      } catch (error) {
        console.error('Failed to parse SSE event:', error, data);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events, preserving incomplete data.
        const events = buffer.split(/\r?\n\r?\n/);

        buffer = events.pop() || '';

        for (const eventBlock of events) {
          processEvent(eventBlock);
        }
      }

      // Flush any remaining decoder data.
      buffer += decoder.decode();

      // Process the final event if the stream ends without a blank line.
      if (buffer.trim()) {
        processEvent(buffer);
      }
    } catch (error) {
      console.error('Streaming connection failed:', error);
      throw error;
    } finally {
      reader.releaseLock();
    }
  },
};
