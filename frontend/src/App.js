import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import lennyLogo from './lenny_logo.webp';
import Turnstile from "react-turnstile";
import ReactMarkdown from 'react-markdown';

function App() {
  const API_BASE = (process.env.REACT_APP_API_URL || "http://localhost:8000").replace(/\/$/, "");
  const TURNSTILE_SITE_KEY = process.env.REACT_APP_TURNSTILE_SITE_KEY || "";

  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [queriesRemaining, setQueriesRemaining] = useState(10);
  const [conversationsRemaining, setConversationsRemaining] = useState(2);
  const [currentConversationLength, setCurrentConversationLength] = useState(0);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const [turnstileToken, setTurnstileToken] = useState(null);

  const [activeTab, setActiveTab] = useState('search'); // 'search' | 'trending' | 'guides'
  const [guides, setGuides] = useState([]);
  const [selectedGuide, setSelectedGuide] = useState(null);
  const [guidesLoading, setGuidesLoading] = useState(false);

  const [trendingQueries, setTrendingQueries] = useState([]);
  const [trendingLoading, setTrendingLoading] = useState(false);

  const [sortBy, setSortBy] = useState('views');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const [turnstileKey, setTurnstileKey] = useState(0);

const resetTurnstile = () => {
  if (!TURNSTILE_SITE_KEY) return;
  setTurnstileToken(null);
  setTurnstileKey((k) => k + 1); // forces Turnstile to remount and re-issue token
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

    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError("Please complete the verification before searching.");
      return;
    }

    const currentQuery = query;
    setQuery('');
    setLoading(true);
    setError(null);

    setMessages(prev => [...prev, { type: 'user', content: currentQuery }]);

    try {
      const headers = TURNSTILE_SITE_KEY
        ? { "X-Turnstile-Token": turnstileToken }
        : {};

      const response = await axios.post(
        `${API_BASE}/search-with-answer`,
        { query: currentQuery, limit: 5 },
        { headers }
      );

      setMessages(prev => [...prev, {
        type: 'assistant',
        content: response.data.answer,
        sources: response.data.sources,
        conversation_length: response.data.conversation_length
      }]);

      setCurrentConversationLength(response.data.conversation_length);
      setQueriesRemaining(response.data.queries_remaining);

      resetTurnstile();
    } catch (err) {
      setMessages(prev => prev.slice(0, -1));

      if (err.response?.status === 429) {
        setError('Daily query limit reached! Try again tomorrow.');
        setQueriesRemaining(0);
      } else if (err.response?.status === 403) {
        setError(err.response?.data?.detail || 'Verification failed. Please retry the verification and search again.');
        resetTurnstile();
      } else {
        setError(err.response?.data?.detail || 'Search failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadGuides = async (sort = 'views') => {
    setGuidesLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/episode-guides?sort_by=${sort}&limit=300`);
      setGuides(response.data.guides || []);
      setSortBy(sort);
    } catch (err) {
      console.error('Failed to load guides', err);
    } finally {
      setGuidesLoading(false);
    }
  };

  const loadTrending = async () => {
    setTrendingLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/trending-questions?days=7&limit=10`);
      setTrendingQueries(response.data.trending || []);
    } catch (err) {
      console.error('Failed to load trending', err);
    } finally {
      setTrendingLoading(false);
    }
  };

  // Load trending when tab is activated
  useEffect(() => {
    if (activeTab === 'trending' && trendingQueries.length === 0) {
      loadTrending();
    }
  }, [activeTab]); // intentionally not including trendingQueries to avoid re-fetch loops

  const viewGuide = async (guideId) => {
    try {
      const response = await axios.get(`${API_BASE}/episode-guides/${guideId}`);
      setSelectedGuide(response.data);
    } catch (err) {
      console.error('Failed to load guide', err);
    }
  };

  useEffect(() => {
    if (activeTab === 'guides' && guides.length === 0) {
      loadGuides();
    }
  }, [activeTab]); // intentionally not including guides to avoid re-fetch loops

  const startNewConversation = async () => {
    if (conversationsRemaining <= 0) {
      setError('You\'ve used both conversations for today. Try again tomorrow!');
      return;
    }

    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError("Please complete the verification before starting a new conversation.");
      return;
    }

    try {
      const headers = TURNSTILE_SITE_KEY
        ? { "X-Turnstile-Token": turnstileToken }
        : {};

      await axios.post(`${API_BASE}/clear-conversation`, {}, { headers });

      setMessages([]);
      setCurrentConversationLength(0);
      setConversationsRemaining(prev => prev - 1);
      setError(null);

      resetTurnstile();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to clear conversation. Please try again.');
      resetTurnstile();
    }
  };

  const exampleQueries = [
    "What's the best pricing strategy for early-stage SaaS?",
    "Should I hire a VP of Product at 20 people?",
    "How to prioritize when everything seems important?",
    "Compare Brian Chesky and Reid Hoffman on company culture",
  ];

  // Safe arrays for modal rendering (prevents .map crash)
  const selectedActionItems = Array.isArray(selectedGuide?.action_items) ? selectedGuide.action_items : [];
  const selectedWhenApplies = Array.isArray(selectedGuide?.when_applies) ? selectedGuide.when_applies : [];
  const selectedFrameworks = Array.isArray(selectedGuide?.frameworks) ? selectedGuide.frameworks : [];

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-content">
          <img src={lennyLogo} alt="Lenny's Logo" className="header-logo" />
          <h1>The Lenny Lens</h1>

          <div className="tabs" style={{ marginLeft: 'auto' }}>
            <button
              className={`tab ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => setActiveTab('search')}
            >
              🔍 Search
            </button>
            <button
              className={`tab ${activeTab === 'trending' ? 'active' : ''}`}
              onClick={() => setActiveTab('trending')}
            >
              🔥 Trending
            </button>
            <button
              className={`tab ${activeTab === 'guides' ? 'active' : ''}`}
              onClick={() => setActiveTab('guides')}
            >
              📚 Episode Guides
            </button>
          </div>
        </div>
      </header>

      {TURNSTILE_SITE_KEY && (
        <div className="turnstile-wrap">
          <Turnstile
            key={turnstileKey}
            sitekey={TURNSTILE_SITE_KEY}
            onVerify={(token) => setTurnstileToken(token)}
            onExpire={() => resetTurnstile()}
            onError={() => resetTurnstile()}
          />
        </div>
      )}

      <main className="App-main">
        {activeTab === 'search' ? (
          // Your existing search UI
          messages.length === 0 ? (
            <div className="landing-page">
              <div className="hero-section">
                <div className="hero-badge">
                  🎙️ 303 episodes • 299 guests • Powered by semantic AI
                </div>

                <h2 className="hero-title">
                  Deep dive into <span className="highlight">303 episodes</span><br />
                  of PM wisdom
                </h2>

                <p className="hero-subtitle">
                  Get answers that help you decide, not just inform.<br />
                  Multiple perspectives synthesized • Contradictions resolved • Actionable playbooks included
                </p>

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

                {error && <div className="error-banner">{error}</div>}

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

                <div className="limits-info">
                  💡 {queriesRemaining} queries • 2 conversations • 5 messages each
                </div>
              </div>
            </div>
          ) : (
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
                              <div className="answer-text">
                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                              </div>
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
          )
        ) : activeTab === 'trending' ? (
          // NEW: Trending Tab
          <div className="trending-tab">
            <div className="trending-container">
              <div className="trending-header">
                <h2>🔥 What PMs Are Asking This Week</h2>
                <p className="trending-subtitle">
                  See the most searched questions from the community
                </p>
              </div>

              {trendingLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#999' }}>
                  Loading trending questions...
                </div>
              ) : trendingQueries.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#999' }}>
                  No trending data yet. Be the first to search!
                </div>
              ) : (
                <div className="trending-list">
                  {trendingQueries.map((item, idx) => (
                    <div
                      key={idx}
                      className="trending-item"
                      onClick={() => {
                        setActiveTab('search');
                        setQuery(item.query);
                      }}
                    >
                      <div className="trending-rank">{idx + 1}</div>
                      <div className="trending-content">
                        <div className="trending-query-text">{item.query}</div>
                        <div className="trending-meta">
                          <span>👁️ {item.count} {item.count === 1 ? 'search' : 'searches'}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          // Episode Guides tab (your existing code)
          <div className="guides-tab">
            <div className="guides-container">
              <div className="guides-header">
                <div>
                  <h2>📚 Episode Action Guides</h2>
                  <p className="guides-subtitle">AI-generated playbooks from 300+ episodes</p>
                </div>
                <div className="sort-controls">
                  <button
                    className={`sort-btn ${sortBy === 'views' ? 'active' : ''}`}
                    onClick={() => loadGuides('views')}
                  >
                    Most Viewed
                  </button>
                  <button
                    className={`sort-btn ${sortBy === 'newest' ? 'active' : ''}`}
                    onClick={() => loadGuides('newest')}
                  >
                    Newest
                  </button>
                  <button
                    className={`sort-btn ${sortBy === 'guest' ? 'active' : ''}`}
                    onClick={() => loadGuides('guest')}
                  >
                    By Guest
                  </button>
                </div>
              </div>

              {guidesLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#999' }}>
                  Loading guides...
                </div>
              ) : (
                <div className="guides-grid">
                  {guides.map((guide) => (
                    <div
                      key={guide.id}
                      className="guide-card"
                      onClick={() => viewGuide(guide.id)}
                    >
                      <div className="view-count-badge">
                        👁️ {guide.views}
                      </div>

                      <div className="guide-guest-name">{guide.guest}</div>
                      <div className="guide-episode-title">{guide.title}</div>
                      <div className="guide-tldr-preview">{guide.tldr}</div>

                      {guide.frameworks && guide.frameworks.length > 0 && (
                        <div className="framework-tags">
                          {guide.frameworks.slice(0, 3).map((fw, idx) => (
                            <span key={idx} className="framework-tag">{fw}</span>
                          ))}
                        </div>
                      )}

                      <div className="guide-meta-info">
                        <span>✅ {guide.action_count} actions</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Modal for Guide Details */}
              {selectedGuide && (
                <div className="modal-overlay" onClick={() => setSelectedGuide(null)}>
                  <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                    <button className="modal-close" onClick={() => setSelectedGuide(null)}>×</button>

                    <div className="modal-header">
                      <h2 className="modal-guest">{selectedGuide.guest}</h2>
                      <p className="modal-title">{selectedGuide.title}</p>
                      <p className="modal-views">👁️ {selectedGuide.views} views</p>
                    </div>

                    <div className="tldr-box">
                      <strong>⚡ TL;DR (30 seconds)</strong>
                      <p>{selectedGuide.tldr}</p>
                    </div>

                    {selectedFrameworks.length > 0 && (
                      <div className="guide-section">
                        <h3>🎯 Key Frameworks</h3>
                        <div className="frameworks-list">
                          {selectedFrameworks.map((fw, idx) => (
                            <div key={idx} className="framework-item">{fw}</div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="guide-section">
                      <h3>✅ Your Action Checklist</h3>
                      <p className="section-desc">Concrete steps you can take this week:</p>

                      {selectedActionItems.length > 0 ? (
                        <ul className="action-checklist">
                          {selectedActionItems.map((item, idx) => (
                            <li key={idx}>
                              <span className="checkbox">☐</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="listen-text">No action items available for this guide yet.</p>
                      )}
                    </div>

                    <div className="guide-section">
                      <h3>⚡ When This Applies</h3>
                      {selectedWhenApplies.length > 0 ? (
                        <ul className="applies-list">
                          {selectedWhenApplies.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="listen-text">No “when this applies” notes available yet.</p>
                      )}
                    </div>

                    <div className="guide-section" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                      <div>
                        <h3>🎧 Listen If:</h3>
                        <p className="listen-text">{selectedGuide.listen_if || '—'}</p>
                      </div>
                      <div>
                        <h3>⏭️ Skip If:</h3>
                        <p className="listen-text">{selectedGuide.skip_if || '—'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </div>
          </div>
        )}
      </main>

      <footer className="App-footer">
        Built with React + FastAPI + PostgreSQL + OpenAI • Semantic search across 303 episodes
      </footer>
    </div>
  );
}

export default App;
