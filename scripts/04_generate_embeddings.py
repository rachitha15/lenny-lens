"""
Generate embeddings for chunks using OpenAI's text-embedding-3-small.
This converts text into vectors that enable semantic search.

COST ESTIMATE:
- text-embedding-3-small: $0.02 per 1M tokens
- ~75 words per chunk = ~100 tokens per chunk
- 35,268 chunks × 100 tokens = ~3.5M tokens
- Estimated cost: $0.07 (7 cents!)
"""

import json
import os
from openai import OpenAI
from tqdm import tqdm
import time
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def generate_embedding(text):
    """Generate embedding for a single text"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Error generating embedding: {e}")
        return None

def generate_embeddings_batch(chunks, batch_size=100, test_mode=True, test_limit=100):
    """Generate embeddings for chunks in batches"""
    
    print("=" * 60)
    print("🧠 GENERATING EMBEDDINGS")
    print("=" * 60)
    print()
    
    if test_mode:
        chunks = chunks[:test_limit]
        print(f"🧪 TEST MODE: Processing only {test_limit} chunks")
        print()
    
    # Estimate cost
    total_words = sum(c['word_count'] for c in chunks)
    estimated_tokens = total_words * 1.3  # Rough estimate
    estimated_cost = (estimated_tokens / 1_000_000) * 0.02
    
    print(f"📊 Estimated tokens: {estimated_tokens:,.0f}")
    print(f"💰 Estimated cost: ${estimated_cost:.4f}")
    print()
    
    if not test_mode:
        confirm = input("Continue with full processing? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return
        print()
    
    embeddings_data = []
    failed = 0
    
    # Process in batches
    for i in tqdm(range(0, len(chunks), batch_size), desc="Processing batches"):
        batch = chunks[i:i + batch_size]
        
        for chunk in batch:
            embedding = generate_embedding(chunk['text'])
            
            if embedding:
                embeddings_data.append({
                    'chunk_id': len(embeddings_data),
                    'episode_guest': chunk['episode_guest'],
                    'episode_title': chunk['episode_title'],
                    'keywords': chunk['keywords'],
                    'chunk_type': chunk['chunk_type'],
                    'text': chunk['text'],
                    'speaker': chunk.get('speaker', ''),
                    'word_count': chunk['word_count'],
                    'embedding': embedding
                })
            else:
                failed += 1
        
        # Rate limiting - be nice to OpenAI API
        time.sleep(0.1)
    
    # Save results
    if test_mode:
        output_file = "data/chunks_with_embeddings_test.json"
    else:
        output_file = "data/chunks_with_embeddings.json"
    
    with open(output_file, 'w') as f:
        json.dump(embeddings_data, f, indent=2)
    
    # Summary
    print()
    print("=" * 60)
    print("📊 EMBEDDING GENERATION SUMMARY")
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
        print(f"Text: {sample['text'][:150]}...")
        print(f"Embedding length: {len(sample['embedding'])} dimensions")
        print(f"First 5 dimensions: {sample['embedding'][:5]}")
    
    print()
    print("=" * 60)
    if test_mode:
        print("✅ TEST COMPLETE! Review results, then run full processing.")
    else:
        print("✅ EMBEDDING GENERATION COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    # Load chunks
    with open('data/chunks.json', 'r') as f:
        chunks = json.load(f)
    
    print(f"Loaded {len(chunks):,} chunks")
    print()
    
    # Run in TEST MODE first
    generate_embeddings_batch(chunks, test_mode=True, test_limit=100)
