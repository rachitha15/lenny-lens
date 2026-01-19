import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import lennyLogo from './lenny_logo.webp';

function App() {
  const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [queriesRemaining, setQueriesRemaining] = useState(10);
  const [conversationsRemaining, setConversationsRemaining] = useState(2);
  const [currentConversationLength, setCurrentConversationLength] = useState(0);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) return;
    
    if (currentConversationLength >= 5) {
      setError('This conversation has reached 5 messages. Start a new conversation to continue!');
      return;
    }
    
    const currentQuery = query;
    setQuery('');
    setLoading(true);
    setError(null);
    
    setMessages(prev => [...prev, { type: 'user', content: currentQuery }]);
    
    try {
      const response = await axios.post(`/search-with-answer`, {
        query: currentQuery,
        limit: 5
      });
      
      setMessages(prev => [...prev, {
        type: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
        conversation_length: response.data.conversation_length
      }]);
      
      setCurrentConversationLength(response.data.conversation_length);
      setQueriesRemaining(response.data.queries_remaining);
    } catch (err) {
      setMessages(prev => prev.slice(0, -1));
      
      if (err.response?.status === 429) {
        setError('⚠️ Daily query limit reached! Try again tomorrow.');
        setQueriesRemaining(0);
      } else {
        setError(err.response?.data?.detail || 'Search failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = async () => {
    if (conversationsRemaining <= 0) {
      setError('You\'ve used both conversations for today. Try again tomorrow!');
      return;
    }
    
    try {
      await axios.post(`${API_BASE}/clear-conversation`);
      setMessages([]);
      setCurrentConversationLength(0);
      setConversationsRemaining(prev => prev - 1);
      setError(null);
    } catch (err) {
      console.error('Failed to clear conversation');
    }
  };

  const exampleQueries = [
    "What's the best pricing strategy for early-stage SaaS?",
    "Should I hire a VP of Product at 20 people?",
    "How to prioritize when everything seems important?",
    "Compare Brian Chesky and Reid Hoffman on company culture",
  ];

  const getUniqueEpisodeCount = (sources) => {
    if (!sources) return 0;
    const uniqueEpisodes = new Set(sources.map(s => s.episode_title));
    return uniqueEpisodes.size;
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-content">
          <img src={lennyLogo} alt="Lenny's Logo" className="header-logo" />
          <h1>The Lenny Lens</h1>
        </div>
      </header>

      <main className="App-main">
        {messages.length === 0 ? (
          // LANDING PAGE - Wisdom Hub Style
          <div className="landing-page">
            <div className="hero-section">
              <div className="hero-badge">
                🎙️ 303 episodes • 299 guests • Powered by semantic AI
              </div>
              
              <h2 className="hero-title">
                Deep dive into <span className="highlight">303 episodes</span><br/>
                of PM wisdom
              </h2>
              
              <p className="hero-subtitle">
                Get answers that help you decide, not just inform.<br/>
                Multiple perspectives synthesized • Contradictions resolved • Actionable playbooks included
              </p>

              {/* Search Input - Prominent */}
              <form onSubmit={handleSearch} className="hero-search-form">
                <div className="search-wrapper">
                  <input
                    type="text"
                    className="hero-search-input"
                    placeholder="Ask anything about product, growth, leadership..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    disabled={loading || queriesRemaining === 0}
                    autoFocus
                  />
                  <button 
                    type="submit" 
                    className="hero-search-button" 
                    disabled={loading || queriesRemaining === 0 || !query.trim()}
                  >
                    {loading ? '...' : '→'}
                  </button>
                </div>
              </form>

              {/* Example Queries - Show decision-focused ones */}
              <div className="example-pills">
                {exampleQueries.map((example, idx) => (
                  <button
                    key={idx}
                    className="example-pill"
                    onClick={() => setQuery(example)}
                  >
                    {example}
                  </button>
                ))}
              </div>

              {/* Limits Info - Subtle at bottom */}
              <div className="limits-info">
                💡 {queriesRemaining} queries • 2 conversations • 5 messages each
              </div>
            </div>
          </div>
        ) : (
          // CONVERSATION VIEW
          <>
            <div className="conversation-status">
              <div className="status-left">
                💬 Message {currentConversationLength}/5
              </div>
              <div className="status-right">
                <span className="queries-badge">{queriesRemaining} queries left</span>
                <button className="new-conversation-btn" onClick={startNewConversation}>
                  ✨ New Conversation ({conversationsRemaining} left)
                </button>
              </div>
            </div>

            <div className="conversation-area">
              <div className="messages-container">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`message-wrapper ${msg.type}`}>
                    {msg.type === 'user' ? (
                      <div className="user-message">
                        <div className="message-bubble">
                          {msg.content}
                        </div>
                      </div>
                    ) : (
                      <div className="assistant-message">
                        <div className="assistant-avatar">
                          <img src={lennyLogo} alt="Lenny" />
                        </div>
                        <div className="assistant-content">
                          <div className="message-bubble">
                            <div className="answer-text">{msg.content}</div>
                          </div>
                          
                          {msg.sources && msg.sources.length > 0 && (
                            <div className="message-sources">
                              <div className="sources-header">📚 Based on insights from:</div>
                              <div className="episode-list">
                                {msg.sources.slice(0, 3).map((source, sidx) => (
                                  <div key={sidx} className="episode-item">
                                    • <strong>{source.episode_guest}:</strong> {source.episode_title}
                                  </div>
                                ))}
                                {msg.sources.length > 3 && (
                                  <div className="more-sources">
                                    +{msg.sources.length - 3} more episode{msg.sources.length - 3 > 1 ? 's' : ''}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                
                {loading && (
                  <div className="message-wrapper assistant">
                    <div className="assistant-message">
                      <div className="assistant-avatar">
                        <img src={lennyLogo} alt="Lenny" />
                      </div>
                      <div className="assistant-content">
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="input-area">
              {error && <div className="error-banner">{error}</div>}
              
              {currentConversationLength >= 5 && (
                <div className="limit-warning">
                  💬 Conversation complete (5/5 messages). 
                  <button onClick={startNewConversation} className="inline-new-btn">
                    Start new conversation
                  </button>
                </div>
              )}
              
              <form onSubmit={handleSearch} className="input-form">
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask a follow-up..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={loading || queriesRemaining === 0 || currentConversationLength >= 5}
                  autoFocus
                />
                <button 
                  type="submit" 
                  className="send-button" 
                  disabled={loading || queriesRemaining === 0 || !query.trim() || currentConversationLength >= 5}
                >
                  {loading ? '...' : '→'}
                </button>
              </form>
            </div>
          </>
        )}
      </main>

      <footer className="App-footer">
        Built with React + FastAPI + PostgreSQL + OpenAI • Semantic search across 303 episodes
      </footer>
    </div>
  );
}

export default App;