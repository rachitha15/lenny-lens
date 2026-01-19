"""
Create intelligent chunks from parsed episodes.
Strategy: Keep Q&A pairs together (Lenny's question + Guest's answer).
This preserves context and makes retrieval more meaningful.
"""

import json
from tqdm import tqdm

def create_qa_chunks(episode_data):
    """Create chunks by pairing questions with answers"""
    
    chunks = []
    turns = episode_data['turns']
    
    i = 0
    while i < len(turns):
        turn = turns[i]
        
        # Check if this is Lenny asking a question
        if turn['speaker'] == 'Lenny' and i + 1 < len(turns):
            question = turn['text']
            answer_turn = turns[i + 1]
            answer = answer_turn['text']
            
            # Create Q&A chunk
            chunk_text = f"Q: {question}\n\nA: {answer}"
            
            chunks.append({
                'episode_guest': episode_data['guest'],
                'episode_title': episode_data['title'],
                'publish_date': episode_data['publish_date'],
                'keywords': episode_data['keywords'],
                'chunk_type': 'qa_pair',
                'text': chunk_text,
                'question': question,
                'answer': answer,
                'speaker': answer_turn['speaker'],
                'word_count': len(chunk_text.split())
            })
            
            i += 2  # Skip both question and answer
        else:
            # Standalone statement (not Q&A)
            chunks.append({
                'episode_guest': episode_data['guest'],
                'episode_title': episode_data['title'],
                'publish_date': episode_data['publish_date'],
                'keywords': episode_data['keywords'],
                'chunk_type': 'statement',
                'text': turn['text'],
                'speaker': turn['speaker'],
                'word_count': len(turn['text'].split())
            })
            i += 1
    
    return chunks

def split_long_chunk(chunk, max_words=800):
    """Split chunks that are too long while preserving meaning"""
    
    if chunk['word_count'] <= max_words:
        return [chunk]
    
    # Split by sentences
    text = chunk['text']
    sentences = text.split('. ')
    
    sub_chunks = []
    current_chunk_text = []
    current_word_count = 0
    
    for sentence in sentences:
        sentence_words = len(sentence.split())
        
        if current_word_count + sentence_words > max_words:
            if current_chunk_text:
                # Create sub-chunk
                sub_chunk = chunk.copy()
                sub_chunk['text'] = '. '.join(current_chunk_text) + '.'
                sub_chunk['word_count'] = current_word_count
                sub_chunks.append(sub_chunk)
                
                # Start new chunk
                current_chunk_text = [sentence]
                current_word_count = sentence_words
        else:
            current_chunk_text.append(sentence)
            current_word_count += sentence_words
    
    # Add remaining text
    if current_chunk_text:
        sub_chunk = chunk.copy()
        sub_chunk['text'] = '. '.join(current_chunk_text) + '.'
        sub_chunk['word_count'] = current_word_count
        sub_chunks.append(sub_chunk)
    
    return sub_chunks

def process_all_episodes_to_chunks():
    """Convert all episodes to chunks"""
    
    print("=" * 60)
    print("🔪 CREATING INTELLIGENT CHUNKS")
    print("=" * 60)
    print()
    
    # Load parsed episodes
    with open('data/parsed_episodes.json', 'r') as f:
        episodes = json.load(f)
    
    print(f"Loaded {len(episodes)} episodes")
    print()
    
    all_chunks = []
    
    # Process each episode
    for episode in tqdm(episodes, desc="Creating chunks"):
        # Create Q&A chunks
        chunks = create_qa_chunks(episode)
        
        # Split long chunks
        final_chunks = []
        for chunk in chunks:
            if chunk['word_count'] > 800:
                sub_chunks = split_long_chunk(chunk, max_words=800)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)
        
        all_chunks.extend(final_chunks)
    
    # Save chunks
    output_file = "data/chunks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    
    # Statistics
    print()
    print("=" * 60)
    print("📊 CHUNKING SUMMARY")
    print("=" * 60)
    print(f"✅ Total chunks created: {len(all_chunks):,}")
    print(f"💾 Saved to: {output_file}")
    print()
    
    # Analyze chunk types
    qa_chunks = [c for c in all_chunks if c['chunk_type'] == 'qa_pair']
    statement_chunks = [c for c in all_chunks if c['chunk_type'] == 'statement']
    
    print("📈 CHUNK STATISTICS:")
    print("-" * 60)
    print(f"  Q&A pairs: {len(qa_chunks):,} ({len(qa_chunks)/len(all_chunks)*100:.1f}%)")
    print(f"  Statements: {len(statement_chunks):,} ({len(statement_chunks)/len(all_chunks)*100:.1f}%)")
    print()
    
    # Word count statistics
    word_counts = [c['word_count'] for c in all_chunks]
    avg_words = sum(word_counts) / len(word_counts)
    max_words = max(word_counts)
    min_words = min(word_counts)
    
    print(f"  Average words per chunk: {avg_words:.1f}")
    print(f"  Max words: {max_words}")
    print(f"  Min words: {min_words}")
    print()
    
    # Show sample chunks
    print("📝 SAMPLE Q&A CHUNK:")
    print("-" * 60)
    sample_qa = [c for c in all_chunks if c['chunk_type'] == 'qa_pair'][0]
    print(f"Episode: {sample_qa['episode_guest']}")
    print(f"Text preview: {sample_qa['text'][:300]}...")
    print()
    
    print("📝 SAMPLE STATEMENT CHUNK:")
    print("-" * 60)
    sample_stmt = statement_chunks[0] if statement_chunks else None
    if sample_stmt:
        print(f"Episode: {sample_stmt['episode_guest']}")
        print(f"Speaker: {sample_stmt['speaker']}")
        print(f"Text preview: {sample_stmt['text'][:200]}...")
    print()
    
    print("=" * 60)
    print("✅ CHUNKING COMPLETE!")
    print("=" * 60)
    print()
    print("Next step: Generate embeddings for these chunks")

if __name__ == "__main__":
    process_all_episodes_to_chunks()
