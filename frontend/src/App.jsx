
import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const activeRequestRef = useRef(0);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (!currentConversationId) {
      setCurrentConversation(null);
      return;
    }

    let cancelled = false;

    const loadConversation = async () => {
      setCurrentConversation(null);

      try {
        const conv = await api.getConversation(currentConversationId);

        if (!cancelled) {
          setCurrentConversation({
            ...conv,
            messages: conv.messages || [],
          });
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load conversation:', error);
          setCurrentConversation(null);
        }
      }
    };

    loadConversation();

    return () => {
      cancelled = true;
    };
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const handleNewConversation = async () => {
    // Reset the previous chat's loading state.
    activeRequestRef.current += 1;
    setIsLoading(false);
    setCurrentConversation(null);

    try {
      const newConv = await api.createConversation();

      setConversations((prev) => [
        {
          id: newConv.id,
          created_at: newConv.created_at,
          message_count: 0,
        },
        ...prev,
      ]);

      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
      setCurrentConversationId(null);
    }
  };

  const handleSelectConversation = (id) => {
    activeRequestRef.current += 1;
    setIsLoading(false);
    setCurrentConversation(null);
    setCurrentConversationId(id);
  };

  const handleSendMessage = async (content) => {
    const conversationId = currentConversationId;

    if (!conversationId || isLoading || !content.trim()) {
      return;
    }

    const requestId = ++activeRequestRef.current;

    setIsLoading(true);

    const userMessage = {
      role: 'user',
      content,
    };

    const assistantMessage = {
      role: 'assistant',
      stage1: null,
      stage2: null,
      stage3: null,
      metadata: null,
      loading: {
        stage1: false,
        stage2: false,
        stage3: false,
      },
    };

    setCurrentConversation((prev) => ({
      ...prev,
      messages: [
        ...(prev?.messages || []),
        userMessage,
        assistantMessage,
      ],
    }));

    const updateLastAssistant = (updater) => {
      if (activeRequestRef.current !== requestId) return;

      setCurrentConversation((prev) => {
        if (!prev) return prev;

        const messages = [...(prev.messages || [])];
        const index = messages.length - 1;

        if (index < 0 || messages[index].role !== 'assistant') {
          return prev;
        }

        messages[index] = updater({ ...messages[index] });

        return { ...prev, messages };
      });
    };

    try {
      await api.sendMessageStream(
        conversationId,
        content,
        (eventType, event) => {
          if (activeRequestRef.current !== requestId) return;

          switch (eventType) {
            case 'stage1_start':
              updateLastAssistant((msg) => ({
                ...msg,
                loading: { ...msg.loading, stage1: true },
              }));
              break;

            case 'stage1_complete':
              updateLastAssistant((msg) => ({
                ...msg,
                stage1: event.data,
                loading: { ...msg.loading, stage1: false },
              }));
              break;

            case 'stage2_start':
              updateLastAssistant((msg) => ({
                ...msg,
                loading: { ...msg.loading, stage2: true },
              }));
              break;

            case 'stage2_complete':
              updateLastAssistant((msg) => ({
                ...msg,
                stage2: event.data,
                metadata: event.metadata,
                loading: { ...msg.loading, stage2: false },
              }));
              break;

            case 'stage3_start':
              updateLastAssistant((msg) => ({
                ...msg,
                loading: { ...msg.loading, stage3: true },
              }));
              break;

            case 'stage3_complete':
              updateLastAssistant((msg) => ({
                ...msg,
                stage3: event.data,
                loading: { ...msg.loading, stage3: false },
              }));
              break;

            case 'title_complete':
              loadConversations();
              break;

            case 'complete':
              setIsLoading(false);
              loadConversations();
              break;

            case 'error':
              console.error('Council stream error:', event.message);
              setIsLoading(false);

              updateLastAssistant((msg) => ({
                ...msg,
                error: event.message || 'Council processing failed.',
                loading: {
                  stage1: false,
                  stage2: false,
                  stage3: false,
                },
              }));
              break;

            default:
              console.log('Unknown event type:', eventType);
          }
        }
      );

      if (activeRequestRef.current === requestId) {
        setIsLoading(false);
      }
    } catch (error) {
      console.error('Failed to send message:', error);

      if (activeRequestRef.current === requestId) {
        setCurrentConversation((prev) => {
          if (!prev) return prev;

          const messages = [...(prev.messages || [])];

          if (messages[messages.length - 1]?.role === 'assistant') {
            messages.pop();
          }

          if (messages[messages.length - 1]?.role === 'user') {
            messages.pop();
          }

          return { ...prev, messages };
        });

        setIsLoading(false);
      }
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />

      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
}

export default App;
