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

def get_db():
    return psycopg2.connect(
        user=os.getenv('DB_USER', 'rachitha.suresh'),
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'lenny_knowledge')
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
async def search_with_answer(request: Request, search_req: SearchRequest):
    """Search with conversation context"""
    
    ip = request.client.host
    rate_check = check_rate_limit(ip, limit=10)
    
    if not rate_check['allowed']:
        raise HTTPException(status_code=429, detail="Daily query limit reached")
    
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

@app.get("/health")
def health_check():
    try:
        conn = get_db()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)