"""
Set up PostgreSQL database with pgvector for semantic search
"""

import psycopg2
import json
from tqdm import tqdm

# Database connection
conn = psycopg2.connect(
    dbname="lenny_knowledge",
    user="rachitha.suresh",
    host="localhost"
)

cur = conn.cursor()

print("=" * 60)
print("🗄️  SETTING UP DATABASE")
print("=" * 60)
print()

# Create chunks table
print("Creating chunks table...")
cur.execute("""
    DROP TABLE IF EXISTS chunks CASCADE;
    
    CREATE TABLE chunks (
        id SERIAL PRIMARY KEY,
        chunk_id INTEGER,
        episode_guest TEXT,
        episode_title TEXT,
        publish_date TEXT,
        keywords TEXT[],
        chunk_type TEXT,
        text TEXT,
        speaker TEXT,
        word_count INTEGER,
        embedding vector(1536),
        created_at TIMESTAMP DEFAULT NOW()
    );
""")

print("✅ Table created")
print()

# Create indexes
print("Creating indexes...")
cur.execute("""
    CREATE INDEX chunks_embedding_idx 
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
    
    CREATE INDEX chunks_guest_idx ON chunks (episode_guest);
    CREATE INDEX chunks_type_idx ON chunks (chunk_type);
""")

print("✅ Indexes created")
print()

conn.commit()

# Load and insert embeddings
print("Loading embeddings from file...")
with open('data/chunks_with_embeddings.json', 'r') as f:
    chunks = json.load(f)

print(f"✅ Loaded {len(chunks):,} chunks")
print()

print("Inserting chunks into database...")
batch_size = 1000

for i in tqdm(range(0, len(chunks), batch_size), desc="Inserting batches"):
    batch = chunks[i:i + batch_size]
    
    for chunk in batch:
        cur.execute("""
            INSERT INTO chunks 
            (chunk_id, episode_guest, episode_title, publish_date, keywords,
             chunk_type, text, speaker, word_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            chunk['chunk_id'],
            chunk['episode_guest'],
            chunk['episode_title'],
            chunk.get('publish_date', ''),
            chunk.get('keywords', []),
            chunk['chunk_type'],
            chunk['text'],
            chunk.get('speaker', ''),
            chunk['word_count'],
            chunk['embedding']
        ))
    
    conn.commit()

# Statistics
print()
print("=" * 60)
print("📊 DATABASE SETUP COMPLETE")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM chunks")
total = cur.fetchone()[0]
print(f"✅ Total chunks in database: {total:,}")

cur.execute("SELECT COUNT(DISTINCT episode_guest) FROM chunks")
guests = cur.fetchone()[0]
print(f"✅ Unique guests: {guests}")

cur.execute("SELECT chunk_type, COUNT(*) FROM chunks GROUP BY chunk_type")
types = cur.fetchall()
print(f"\n📝 Chunk Types:")
for type_name, count in types:
    print(f"  {type_name}: {count:,}")

print()
print("=" * 60)
print("✅ READY FOR VECTOR SEARCH!")
print("=" * 60)

cur.close()
conn.close()
