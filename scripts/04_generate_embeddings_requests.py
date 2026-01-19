import os
import json
import requests
from tqdm import tqdm
import time
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = os.getenv('OPENAI_API_KEY')

def generate_embedding(text):
    """Generate embedding using direct API call - SSL verification disabled"""
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "input": text,
        "model": "text-embedding-3-small"
    }
    
    try:
        # verify=False disables SSL verification
        response = requests.post(url, headers=headers, json=data, timeout=30, verify=False)
        response.raise_for_status()
        return response.json()['data'][0]['embedding']
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

print("=" * 60)
print("🧠 GENERATING EMBEDDINGS (SSL Verification Disabled)")
print("=" * 60)
print()

# Test API connection
print("Testing API connection...")
test_emb = generate_embedding("test")
if test_emb:
    print(f"✅ API works! Embedding dimensions: {len(test_emb)}")
    print()
else:
    print("❌ API connection failed")
    exit(1)

# Load chunks
print("Loading chunks...")
with open('data/chunks.json', 'r') as f:
    chunks = json.load(f)

print(f"✅ Loaded {len(chunks):,} chunks")
print()

# Estimate cost
total_words = sum(c['word_count'] for c in chunks)
estimated_tokens = total_words * 1.3
estimated_cost = (estimated_tokens / 1_000_000) * 0.02

print(f"📊 Total chunks: {len(chunks):,}")
print(f"📊 Estimated tokens: {estimated_tokens:,.0f}")
print(f"💰 Estimated cost: ${estimated_cost:.4f}")
print()

# Start with TEST MODE
TEST_MODE = False  # Change to False for full run

if TEST_MODE:
    chunks = chunks[:100]
    print(f"🧪 TEST MODE: Processing only {len(chunks)} chunks")
    print()

embeddings_data = []
failed = 0

print("🔄 Starting embedding generation...")
print()

# Process chunks
for i, chunk in enumerate(tqdm(chunks, desc="Processing chunks")):
    embedding = generate_embedding(chunk['text'])
    
    if embedding:
        embeddings_data.append({
            'chunk_id': i,
            'episode_guest': chunk['episode_guest'],
            'episode_title': chunk['episode_title'],
            'publish_date': chunk.get('publish_date', ''),
            'keywords': chunk.get('keywords', []),
            'chunk_type': chunk['chunk_type'],
            'text': chunk['text'],
            'speaker': chunk.get('speaker', ''),
            'word_count': chunk['word_count'],
            'embedding': embedding
        })
    else:
        failed += 1
    
    # Rate limiting
    time.sleep(0.1)

# Save results
output_file = 'data/chunks_with_embeddings_test.json' if TEST_MODE else 'data/chunks_with_embeddings.json'

print()
print("💾 Saving to file...")

with open(output_file, 'w') as f:
    json.dump(embeddings_data, f, indent=2)

# Summary
print()
print("=" * 60)
print("📊 EMBEDDING GENERATION COMPLETE!")
print("=" * 60)
print(f"✅ Successfully processed: {len(embeddings_data):,} chunks")
print(f"❌ Failed: {failed}")
print(f"💾 Saved to: {output_file}")
print()

# Show sample
if embeddings_data:
    sample = embeddings_data[0]
    print("📝 SAMPLE EMBEDDED CHUNK:")
    print("-" * 60)
    print(f"Guest: {sample['episode_guest']}")
    print(f"Type: {sample['chunk_type']}")
    print(f"Text: {sample['text'][:100]}...")
    print(f"Embedding dimensions: {len(sample['embedding'])}")
    print(f"First 5 values: {sample['embedding'][:5]}")
print()

if TEST_MODE:
    print("=" * 60)
    print("✅ TEST SUCCESSFUL!")
    print("To process all chunks, edit the script:")
    print("  Change: TEST_MODE = False")
    print("  To:     TEST_MODE = False")
    print("=" * 60)
