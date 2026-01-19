import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [queriesRemaining, setQueriesRemaining] = useState(10);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [comparisonMode, setComparisonMode] = useState(false);
  const [guest1, setGuest1] = useState('');
  const [guest2, setGuest2] = useState('');
  const [comparisonTopic, setComparisonTopic] = useState('');
  const [comparisonResult, setComparisonResult] = useState(null);
  const [guestList, setGuestList] = useState([]);

  React.useEffect(() => {
    // Load guest list for autocomplete
    axios.get('http://localhost:8000/guests')
      .then(response => setGuestList(response.data.guests))
      .catch(err => console.error('Failed to load guests'));
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    setComparisonResult(null);
    
    try {
      const response = await axios.post('http://localhost:8000/search-with-answer', {
        query: query,
        limit: 5
      });
      
      setResult(response.data);
      if (response.data.queries_remaining !== undefined) {
        setQueriesRemaining(response.data.queries_remaining);
      }
    } catch (err) {
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

  const handleCompare = async () => {
    if (!guest1 || !guest2 || !comparisonTopic) return;
    
    setLoading(true);
    setError(null);
    setComparisonResult(null);
    setResult(null);
    
    try {
      const response = await axios.post('http://localhost:8000/compare', {
        guest1: guest1,
        guest2: guest2,
        topic: comparisonTopic,
        limit: 3
      });
      
      setComparisonResult(response.data);
      if (response.data.queries_remaining !== undefined) {
        setQueriesRemaining(response.data.queries_remaining);
      }
    } catch (err) {
      if (err.response?.status === 429) {
        setError('⚠️ Daily query limit reached! Try again tomorrow.');
        setQueriesRemaining(0);
      } else if (err.response?.status === 404) {
        setError(err.response?.data?.detail || 'Guest not found in podcast episodes.');
      } else {
        setError(err.response?.data?.detail || 'Comparison failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const exampleQueries = [
    "How to know if I have product-market fit?",
    "What did Elena Verna say about pricing?",
    "How to prioritize features when everything is important?",
    "Brian Chesky's approach to company culture",
  ];

  const getUniqueEpisodeCount = () => {
    if (!result || !result.sources) return 0;
    const uniqueEpisodes = new Set(result.sources.map(s => s.episode_title));
    return uniqueEpisodes.size;
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🎙️ Lenny's Podcast Knowledge Engine</h1>
        <p>Search 303 episodes of PM wisdom with AI</p>
      </header>

      <main className="App-main">
        {/* MODE SELECTOR */}
        <div className="mode-selector">
          <button 
            className={`mode-button ${!comparisonMode ? 'active' : ''}`}
            onClick={() => {
              setComparisonMode(false);
              setError(null);
            }}
          >
            🔍 Search
          </button>
          <button 
            className={`mode-button ${comparisonMode ? 'active' : ''}`}
            onClick={() => {
              setComparisonMode(true);
              setError(null);
              setResult(null);
              setComparisonResult(null);
            }}
          >
            ⚖️ Compare Guests
          </button>
        </div>

        {/* CONDITIONAL: Search Form OR Comparison Form */}
        {!comparisonMode ? (
          // SEARCH MODE
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              className="search-input"
              placeholder='Try: "What did Elena Verna say about pricing?" or "How to do customer discovery?"'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="search-button" disabled={loading || queriesRemaining === 0}>
              {loading ? '🔍 Searching...' : 'Search'}
            </button>
          </form>
        ) : (
          // COMPARISON MODE
          <div className="comparison-form">
            <h3 className="comparison-title">
              Compare what two guests say about any topic
            </h3>
            
            <div className="comparison-inputs">
              <div className="comparison-row">
                <label>Guest 1:</label>
                <input
                  type="text"
                  value={guest1}
                  onChange={(e) => setGuest1(e.target.value)}
                  list="guests-datalist"
                  placeholder="Type to search... (e.g., Brian Chesky)"
                  className="comparison-input"
                />
              </div>
              
              <div className="vs-divider">VS</div>
              
              <div className="comparison-row">
                <label>Guest 2:</label>
                <input
                  type="text"
                  value={guest2}
                  onChange={(e) => setGuest2(e.target.value)}
                  list="guests-datalist"
                  placeholder="Type to search... (e.g., Elena Verna)"
                  className="comparison-input"
                />
              </div>
              
              <div className="comparison-row">
                <label>Topic:</label>
                <input
                  type="text"
                  value={comparisonTopic}
                  onChange={(e) => setComparisonTopic(e.target.value)}
                  placeholder="e.g., pricing strategy, product vision, company culture"
                  className="comparison-input"
                />
              </div>
              
              <button 
                className="compare-button"
                onClick={handleCompare}
                disabled={loading || !guest1 || !guest2 || !comparisonTopic || queriesRemaining === 0}
              >
                {loading ? '⚖️ Comparing...' : 'Compare Perspectives'}
              </button>
            </div>
            
            {/* Datalist for autocomplete */}
            <datalist id="guests-datalist">
              {guestList.map(g => (
                <option key={g.name} value={g.name} />
              ))}
            </datalist>
          </div>
        )}

        {/* Query counter */}
        {queriesRemaining !== null && (
          <div className="query-counter">
            {queriesRemaining > 0 ? (
              <p>🔥 {queriesRemaining} {queriesRemaining === 1 ? 'query' : 'queries'} remaining today</p>
            ) : (
              <p>⚠️ You've used all your queries for today. Come back tomorrow!</p>
            )}
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {loading && (
          <div className="loading-message">
            <div className="spinner"></div>
            <p>
              {comparisonMode 
                ? 'Comparing perspectives and synthesizing analysis...'
                : 'Searching through 303 episodes and synthesizing answer with AI...'}
            </p>
          </div>
        )}

        {/* REGULAR SEARCH RESULTS */}
        {result && !comparisonMode && (
          <div className="results">
            <div className="answer-section">
              <h2>💡 Answer</h2>
              <div className="answer-text">
                {result.answer}
              </div>
            </div>

            <div className="sources-section">
              <h3>
                📚 Sources
                {getUniqueEpisodeCount() === 1 ? (
                  <span className="episode-count"> from 1 episode</span>
                ) : (
                  <span className="episode-count"> from {getUniqueEpisodeCount()} episodes</span>
                )}
              </h3>
              
              {result.sources.map((source, idx) => (
                <div key={idx} className="source-card">
                  <div className="source-header">
                    <div className="source-info">
                      <strong>{source.episode_guest}</strong>
                      <div className="source-meta">
                        {source.chunk_type === 'qa_pair' ? '💬 Q&A Discussion' : '💭 Key Statement'}
                      </div>
                    </div>
                    <span className="similarity">
                      {(source.similarity * 100).toFixed(1)}% relevant
                    </span>
                  </div>
                  <div className="source-title">
                    {source.episode_title}
                  </div>
                  <div className="source-excerpt">
                    "{source.text.substring(0, 250)}..."
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* COMPARISON RESULTS */}
        {comparisonResult && comparisonMode && (
          <div className="comparison-results">
            <h2 className="comparison-header">
              ⚖️ Comparing Perspectives on: {comparisonResult.topic}
            </h2>
            
            <div className="comparison-grid">
              {/* Guest 1 Perspective */}
              <div className="guest-perspective">
                <h3>{comparisonResult.guest1.name}</h3>
                <div className="perspective-content">
                  {comparisonResult.guest1.summary}
                </div>
                {comparisonResult.guest1.sources && comparisonResult.guest1.sources.length > 0 && (
                  <div className="perspective-sources">
                    <h4>Key Sources:</h4>
                    {comparisonResult.guest1.sources.slice(0, 2).map((source, idx) => (
                      <div key={idx} className="mini-source">
                        <strong>{source.episode_title}</strong>
                        <p>"{source.text.substring(0, 120)}..."</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
              {/* Guest 2 Perspective */}
              <div className="guest-perspective">
                <h3>{comparisonResult.guest2.name}</h3>
                <div className="perspective-content">
                  {comparisonResult.guest2.summary}
                </div>
                {comparisonResult.guest2.sources && comparisonResult.guest2.sources.length > 0 && (
                  <div className="perspective-sources">
                    <h4>Key Sources:</h4>
                    {comparisonResult.guest2.sources.slice(0, 2).map((source, idx) => (
                      <div key={idx} className="mini-source">
                        <strong>{source.episode_title}</strong>
                        <p>"{source.text.substring(0, 120)}..."</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            {/* Comparison Analysis */}
            <div className="comparison-analysis">
              <h3>🎯 Analysis: Similarities & Differences</h3>
              <div className="analysis-text">
                {comparisonResult.comparison}
              </div>
            </div>
          </div>
        )}

        {/* PLACEHOLDER - Show when no results */}
        {!result && !comparisonResult && !loading && !error && (
          <div className="placeholder">
            <div className="placeholder-icon">💡</div>
            {!comparisonMode ? (
              <>
                <h3>Ask me anything about PM!</h3>
                <p className="placeholder-subtitle">
                  I can answer general questions or tell you what specific guests said
                </p>
                <div className="example-queries">
                  {exampleQueries.map((example, idx) => (
                    <button
                      key={idx}
                      className="example-query"
                      onClick={() => {
                        setQuery(example);
                        document.querySelector('.search-input').focus();
                      }}
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <h3>Compare Guest Perspectives</h3>
                <p className="placeholder-subtitle">
                  See how different PM leaders approach the same topic
                </p>
                <div className="example-comparisons">
                  <button 
                    className="example-query"
                    onClick={() => {
                      setGuest1('Brian Chesky');
                      setGuest2('Elena Verna');
                      setComparisonTopic('company culture');
                    }}
                  >
                    Brian Chesky vs Elena Verna on "company culture"
                  </button>
                  <button 
                    className="example-query"
                    onClick={() => {
                      setGuest1('Adam Fishman');
                      setGuest2('Casey Winters');
                      setComparisonTopic('growth strategy');
                    }}
                  >
                    Adam Fishman vs Casey Winters on "growth strategy"
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </main>

      <footer className="App-footer">
        <p>Built with React + FastAPI + PostgreSQL + pgvector + OpenAI</p>
        <p style={{fontSize: '0.85rem', opacity: 0.8, marginTop: '0.5rem'}}>
          Semantic search across 303 episodes • 299 guests • Powered by AI
        </p>
      </footer>
    </div>
  );
}

export default App;