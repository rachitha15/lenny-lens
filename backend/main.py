"""
The Lenny Lens API - Secure & Improved
API key from environment + better prompts for actionable answers
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import requests
import urllib3
import re
import os
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from rate_limiter import check_rate_limit
from fastapi import Header, HTTPException


# Load environment variables
load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="The Lenny Lens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API key from environment variable (SECURE!)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in .env file")

# Session storage
conversation_sessions = defaultdict(list)
def verify_turnstile(token: str):
    secret = os.getenv("TURNSTILE_SECRET_KEY")

    if not secret:
        raise RuntimeError("TURNSTILE_SECRET_KEY is not set")

    if not token:
        print("⚠️ No Turnstile token - skipping verification (dev mode)")
        return

    resp = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={"secret": secret, "response": token},
        timeout=10,
    )

    data = resp.json()
    if not data.get("success"):
        raise HTTPException(status_code=403, detail="Verification failed")


def get_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(
        db_url
    )

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

def extract_guest_name(query):
    """Extract guest name from query"""
    q = query
    
    patterns = [
        r"what (?:did|does) ([A-Z][a-z]+(?: [A-Z][a-z]+)*) (?:say|think|mention|discuss)",
        r"([A-Z][a-z]+(?: [A-Z][a-z]+)*)'s (?:approach|view|perspective|thoughts?)",
        r"according to ([A-Z][a-z]+(?: [A-Z][a-z]+)*)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def extract_topic_from_guest_query(query):
    """Extract the topic from guest-specific queries"""
    patterns = [
        r"say about (.+?)[\?]?$",
        r"think about (.+?)[\?]?$",
        r"mention about (.+?)[\?]?$",
        r"discuss (.+?)[\?]?$",
        r"on (.+?)[\?]?$",
        r"regarding (.+?)[\?]?$"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            topic = match.group(1).strip()
            # Remove trailing question marks or punctuation
            topic = re.sub(r'[?.!]+$', '', topic)
            return topic
    
    return None

def detect_query_type(query):
    """Detect query type"""
    q = query.lower()
    
    if any(phrase in q for phrase in ['what did', 'what does', "'s approach", "'s view"]):
        if extract_guest_name(query):
            return 'guest_specific'
    
    if any(w in q for w in ['compare', 'vs', 'versus', 'difference', 'contrast']):
        return 'comparison'
    elif q.startswith('how to') or q.startswith('how do') or q.startswith('how can'):
        return 'how_to'
    elif q.startswith('what is') or q.startswith('what are'):
        return 'definition'
    else:
        return 'general'

def generate_query_embedding(query_text):
    """Convert query to embedding"""
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {"input": query_text, "model": "text-embedding-3-small"}
    
    try:
        response = requests.post(url, headers=headers, json=data, verify=False, timeout=30)
        response.raise_for_status()
        return response.json()['data'][0]['embedding']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

def search_similar_chunks(query_embedding, limit=5, filter_guest=None):
    """Search with optional guest filter"""
    
    conn = get_db()
    cur = conn.cursor()
    
    if filter_guest:
        cur.execute("""
            SELECT id, episode_guest, episode_title, chunk_type, text, speaker, keywords,
                   1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            WHERE episode_guest ILIKE %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, f"%{filter_guest}%", query_embedding, limit))
    else:
        cur.execute("""
            SELECT id, episode_guest, episode_title, chunk_type, text, speaker, keywords,
                   1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, limit))
    
    results = cur.fetchall()
    
    chunks = []
    for row in results:
        chunks.append({
            'id': row[0],
            'episode_guest': row[1],
            'episode_title': row[2],
            'chunk_type': row[3],
            'text': row[4],
            'speaker': row[5],
            'keywords': row[6] if row[6] else [],
            'similarity': float(row[7])
        })
    
    cur.close()
    conn.close()
    
    return chunks

def synthesize_answer(query, chunks, conversation_context=None):
    """Adaptive synthesis - includes relevant sections based on content"""
    
    query_type = detect_query_type(query)
    guest_name = extract_guest_name(query) if query_type == 'guest_specific' else None
    
    chunks_context = "\n\n".join([
        f"[{chunk['episode_guest']} - {chunk['episode_title']}]\n{chunk['text']}"
        for chunk in chunks[:7]
    ])
    
    context_section = ""
    if conversation_context:
        context_section = f"""Previous conversation:
{conversation_context}

This is a follow-up question.
"""
    
    # Universal adaptive prompt
    base_prompt = f"""{context_section}
You are The Lenny Lens - an AI advisor that helps PMs make decisions, not just learn information.

Question: {query}

Sources:
{chunks_context}

Provide a structured answer that ADAPTS based on the content:

**ALWAYS INCLUDE:**
1. Main synthesized answer (2-3 paragraphs)

**INCLUDE IF RELEVANT:**
2. **Different Perspectives:** (only if multiple valid approaches exist)
   • Use bullet points to show distinct approaches
   • Include who recommends each and their context
   
3. **Contradictions to Consider:** (only if guests disagree or warn against something)
   • Show the tension clearly
   • Explain when each perspective applies
   
4. **Credibility Context:** (only if claims need backing or user is making decisions)
   • Who said this + their relevant experience
   • What companies/results validate this
   
5. **Actionable Playbook:** (only if query needs practical steps)
   • Concrete steps with timeline
   • Specific metrics or checkpoints
   • Based on what guests actually did

**FORMATTING RULES:**
- Cite every claim: [Guest Name, Episode: Full title]
- Use bullet points for clarity
- Be specific: include numbers, company names, timeframes
- Don't add sections that aren't relevant to this query

Answer:"""
    
    # Type-specific overrides for better structure
    if query_type == 'guest_specific':
        # For guest queries, focus on THEIR specific view
        base_prompt = f"""{context_section}
Focus on {guest_name}'s SPECIFIC insights.

Question: {query}

Sources (from {guest_name}):
{chunks_context}

Structure:

**{guest_name}'s Perspective:**
[2-3 sentences on their specific approach]

**Key Insights:**
• **[Specific method/framework]:** [How they use it with concrete example, 2-3 sentences]
• **[Another insight]:** [Details with numbers/names]

**Actionable Takeaway:** [One thing to do Monday based on their advice]

Cite: [{guest_name}, Episode: Full title]

Be SPECIFIC: Include company names, metrics, frameworks by name, real stories."""
    
    elif query_type == 'comparison':
        # For comparisons, force structured comparison
        base_prompt = f"""{context_section}
Compare perspectives with concrete examples.

Question: {query}

Sources:
{chunks_context}

Structure:

[Overview - core similarity and key difference]

**Compare and Contrast:**
• **[Dimension 1]:**
   • **[Person A]:** [Specific approach with example, 2-3 sentences]
   • **[Person B]:** [Contrasting approach with example]
• **[Dimension 2]:**
   • **[Person A]:** [Their method]
   • **[Person B]:** [Different method]

**When to Use Each:** [Practical scenarios]

Cite: [Guest, Episode: Full title]"""
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": base_prompt}],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, verify=False, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

@app.get("/")
def root():
    return {"message": "The Lenny Lens API", "status": "healthy"}

@app.post("/search-with-answer")
async def search_with_answer(request: Request, search_req: SearchRequest,x_turnstile_token: str = Header(default="")):
    """Search with conversation context"""
    verify_turnstile(x_turnstile_token)
    
    ip = request.client.host
    rate_check = check_rate_limit(ip, limit=10)
    
    if not rate_check['allowed']:
        raise HTTPException(status_code=429, detail="Daily query limit reached")
    
    try:
        import hashlib
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        
        conn_log = get_db()
        cur_log = conn_log.cursor()
        cur_log.execute(
            "INSERT INTO query_log (query, ip_hash) VALUES (%s, %s)",
            (search_req.query, ip_hash)
        )
        conn_log.commit()
        cur_log.close()
        conn_log.close()
    except Exception as e:
        pass
    
    if not search_req.query or len(search_req.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")
    
    session = conversation_sessions[ip]
    
    if len(session) >= 5:
        raise HTTPException(status_code=400, detail="Conversation limit reached (5 messages)")
    
    search_query = search_req.query
    conversation_context = None
    
    if session:
        recent = session[-2:]
        conversation_context = "\n".join([
            f"Q: {qa['query']}\nA: {qa['answer'][:250]}..."
            for qa in recent
        ])
        
        if len(search_req.query.split()) < 5:
            search_query = f"{recent[-1]['query']} {search_req.query}"
    
    query_type = detect_query_type(search_req.query)
    detected_guest = extract_guest_name(search_req.query) if query_type == 'guest_specific' else None
    detected_topic = extract_topic_from_guest_query(search_req.query) if query_type == 'guest_specific' else None
    
    # Guest-specific: search for TOPIC within guest's content
    if query_type == 'guest_specific' and detected_topic:
        limit = 10
        filter_guest = detected_guest
        search_query = detected_topic  # Search for topic, not full question!
    elif query_type == 'guest_specific':
        limit = 10
        filter_guest = detected_guest
    else:
        limit = 5
        filter_guest = None
    
    query_embedding = generate_query_embedding(search_query)
    chunks = search_similar_chunks(query_embedding, limit=limit, filter_guest=filter_guest)
    
    # Quality filter
    high_quality_chunks = [c for c in chunks if c['similarity'] > 0.35]
    if len(high_quality_chunks) < 3:
        high_quality_chunks = chunks[:3]
    
    answer = synthesize_answer(search_req.query, high_quality_chunks, conversation_context)
    
    session.append({
        'query': search_req.query,
        'answer': answer,
        'timestamp': datetime.now()
    })
    
    conversation_sessions[ip] = session[-5:]
    
    # Clean old sessions
    cutoff = datetime.now() - timedelta(hours=24)
    for ip_addr in list(conversation_sessions.keys()):
        conversation_sessions[ip_addr] = [
            qa for qa in conversation_sessions[ip_addr]
            if qa['timestamp'] > cutoff
        ]
    
    return {
        "query": search_req.query,
        "answer": answer,
        "sources": high_quality_chunks[:5],
        "total_results": len(high_quality_chunks),
        "conversation_length": len(session),
        "is_followup": len(session) > 1,
        "queries_remaining": rate_check['queries_remaining']
    }

@app.post("/clear-conversation")
async def clear_conversation(request: Request):
    ip = request.client.host
    conversation_sessions[ip] = []
    return {"status": "cleared"}

@app.get("/guests")
def get_all_guests():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT episode_guest, COUNT(*) FROM chunks GROUP BY episode_guest ORDER BY episode_guest")
    guests = [{"name": row[0], "chunk_count": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return {"guests": guests}

@app.get("/stats")
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT episode_guest) FROM chunks")
    unique_guests = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"total_chunks": total_chunks, "unique_guests": unique_guests}

@app.get("/trending-questions")
async def get_trending_questions(days: int = 7, limit: int = 10):
    """Get most searched questions in the last N days"""
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get hot questions from last N days
    cur.execute("""
        SELECT 
            query,
            COUNT(*) as search_count,
            MIN(created_at) as first_searched,
            MAX(created_at) as last_searched
        FROM query_log
        WHERE created_at > NOW() - INTERVAL '%s days'
        GROUP BY query
        HAVING COUNT(*) >= 1
        ORDER BY COUNT(*) DESC, MAX(created_at) DESC
        LIMIT %s
    """, (days, limit))
    
    trending = []
    for row in cur.fetchall():
        trending.append({
            'query': row[0],
            'count': row[1],
            'first_searched': row[2].isoformat() if row[2] else None,
            'last_searched': row[3].isoformat() if row[3] else None
        })
    
    cur.close()
    conn.close()
    
    return {"trending": trending, "period_days": days}

@app.get("/health")
def health_check():
    try:
        conn = get_db()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    
# Get all episode guides
@app.get("/episode-guides")
async def get_episode_guides(sort_by: str = "views", limit: int = 300):
    """Get episode guides sorted by views, newest, or guest"""
    
    conn = get_db()
    cur = conn.cursor()
    
    # Determine sort order
    if sort_by == "views":
        order = "view_count DESC, created_at DESC"
    elif sort_by == "newest":
        order = "created_at DESC"
    elif sort_by == "guest":
        order = "episode_guest ASC"
    else:
        order = "view_count DESC"
    
    cur.execute(f"""
        SELECT 
            id, episode_guest, episode_title, tldr,
            key_frameworks, array_length(action_items, 1) as action_count,
            view_count
        FROM episode_guides
        ORDER BY {order}
        LIMIT %s
    """, (limit,))
    
    guides = []
    for row in cur.fetchall():
        guides.append({
            'id': row[0],
            'guest': row[1],
            'title': row[2],
            'tldr': row[3],
            'frameworks': row[4] if row[4] else [],
            'action_count': row[5] if row[5] else 0,
            'views': row[6]
        })
    
    cur.close()
    conn.close()
    
    return {"guides": guides, "total": len(guides)}

# Get single guide details + increment view
@app.get("/episode-guides/{guide_id}")
async def get_guide_detail(guide_id: int, request: Request):
    """Get full guide details and track view"""
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get guide
    cur.execute("""
        SELECT 
            id, episode_guest, episode_title, tldr,
            key_frameworks, action_items, when_applies,
            listen_if, skip_if, view_count
        FROM episode_guides
        WHERE id = %s
    """, (guide_id,))
    
    row = cur.fetchone()
    
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Guide not found")
    
    guide = {
        'id': row[0],
        'guest': row[1],
        'title': row[2],
        'tldr': row[3],
        'frameworks': row[4] if row[4] else [],
        'action_items': row[5] if row[5] else [],
        'when_applies': row[6] if row[6] else [],
        'listen_if': row[7],
        'skip_if': row[8],
        'views': row[9]
    }
    
    # Track view (hash IP for privacy)
    try:
        import hashlib
        ip = request.client.host
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        
        # Insert view record
        cur.execute(
            "INSERT INTO guide_views (guide_id, ip_hash) VALUES (%s, %s)",
            (guide_id, ip_hash)
        )
        
        # Increment view count
        cur.execute(
            "UPDATE episode_guides SET view_count = view_count + 1 WHERE id = %s",
            (guide_id,)
        )
        
        conn.commit()
        guide['views'] += 1  # Update returned count
    except:
        conn.rollback()
    
    cur.close()
    conn.close()
    
    return guide

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)