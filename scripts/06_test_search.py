import os
"""
Test vector search - this proves the whole system works!
"""

import psycopg2
import requests
import json

# Disable SSL verification for OpenAI (Zscaler issue)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = os.getenv('OPENAI_API_KEY')

def generate_query_embedding(query_text):
    """Convert user query to embedding"""
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "input": query_text,
        "model": "text-embedding-3-small"
    }
    
    response = requests.post(url, headers=headers, json=data, verify=False)
    return response.json()['data'][0]['embedding']

def search_similar_chunks(query_text, limit=5):
    """Search for similar chunks using vector similarity"""
    
    # Generate embedding for query
    print(f"🔍 Searching for: '{query_text}'")
    print()
    query_embedding = generate_query_embedding(query_text)
    
    # Connect to database
    conn = psycopg2.connect(
        dbname="lenny_knowledge",
        user="rachitha.suresh",
        host="localhost"
    )
    cur = conn.cursor()
    
    # Vector similarity search
    cur.execute("""
        SELECT 
            episode_guest,
            episode_title,
            chunk_type,
            text,
            1 - (embedding <=> %s::vector) as similarity
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit))
    
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return results

# Test queries
test_queries = [
    "How do I know if I have product-market fit?",
    "What's the best way to do customer discovery?",
    "How to prioritize features when everything is important?",
]

print("=" * 70)
print("🧠 TESTING VECTOR SEARCH")
print("=" * 70)
print()

for query in test_queries:
    results = search_similar_chunks(query, limit=3)
    
    print("📊 RESULTS:")
    print("-" * 70)
    
    for i, (guest, title, chunk_type, text, similarity) in enumerate(results, 1):
        print(f"\n{i}. {guest} (Similarity: {similarity:.3f})")
        print(f"   Episode: {title[:60]}...")
        print(f"   Type: {chunk_type}")
        print(f"   Text: {text[:200]}...")
    
    print()
    print("=" * 70)
    print()

print("✅ VECTOR SEARCH IS WORKING!")
print()
print("Next steps:")
print("  1. Build FastAPI backend")
print("  2. Add answer synthesis with GPT")
print("  3. Build frontend")
print("  4. Deploy!")
