"""
Parse all 303 episode transcripts and save to JSON.
This creates a structured dataset we'll use for embeddings and knowledge extraction.
"""

import yaml
import os
import json
from pathlib import Path
from tqdm import tqdm
from datetime import date, datetime

def parse_transcript(file_path):
    """Parse a single transcript markdown file"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parts = content.split('---')
    
    if len(parts) < 3:
        return None
    
    frontmatter_text = parts[1]
    transcript_text = '---'.join(parts[2:])
    
    try:
        metadata = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        print(f"⚠️ Error parsing YAML in {file_path}: {e}")
        return None
    
    guest_folder = Path(file_path).parent.name
    
    # Convert date objects to strings
    publish_date = metadata.get('publish_date', '')
    if isinstance(publish_date, (date, datetime)):
        publish_date = publish_date.isoformat()
    
    return {
        'guest_folder': guest_folder,
        'guest': metadata.get('guest', guest_folder),
        'title': metadata.get('title', ''),
        'youtube_url': metadata.get('youtube_url', ''),
        'publish_date': publish_date,
        'keywords': metadata.get('keywords', []),
        'duration': metadata.get('duration', ''),
        'description': metadata.get('description', ''),
        'transcript': transcript_text.strip(),
        'transcript_length': len(transcript_text.strip()),
        'file_path': str(file_path)
    }

def extract_speaker_turns(transcript_text):
    """Extract individual speaker turns from transcript"""
    
    lines = transcript_text.split('\n')
    turns = []
    current_speaker = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        
        if not line or line.startswith('#'):
            continue
        
        if '(' in line and '):' in line:
            if current_speaker and current_text:
                turns.append({
                    'speaker': current_speaker,
                    'text': ' '.join(current_text).strip()
                })
            
            speaker_part = line.split('(')[0].strip()
            timestamp_and_text = line.split('):')
            
            if len(timestamp_and_text) > 1:
                current_speaker = speaker_part
                current_text = [timestamp_and_text[1].strip()]
            else:
                current_text.append(line)
        else:
            if current_speaker:
                current_text.append(line)
    
    if current_speaker and current_text:
        turns.append({
            'speaker': current_speaker,
            'text': ' '.join(current_text).strip()
        })
    
    return turns

def process_all_episodes():
    """Process all episodes in the transcripts directory"""
    
    episodes_dir = Path("data/lennys-podcast-transcripts/episodes")
    
    if not episodes_dir.exists():
        print(f"❌ Episodes directory not found: {episodes_dir}")
        return
    
    # Get all episode folders
    episode_folders = [f for f in episodes_dir.iterdir() if f.is_dir()]
    
    print(f"Found {len(episode_folders)} episode folders")
    print()
    
    all_episodes = []
    failed = []
    
    # Process each episode
    for folder in tqdm(episode_folders, desc="Processing episodes"):
        transcript_file = folder / "transcript.md"
        
        if not transcript_file.exists():
            failed.append(str(folder))
            continue
        
        episode_data = parse_transcript(transcript_file)
        
        if episode_data:
            # Extract speaker turns
            turns = extract_speaker_turns(episode_data['transcript'])
            episode_data['turns'] = turns
            episode_data['num_turns'] = len(turns)
            
            all_episodes.append(episode_data)
        else:
            failed.append(str(folder))
    
    # Save results
    output_file = "data/parsed_episodes.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_episodes, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print()
    print("=" * 60)
    print("📊 PROCESSING SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully parsed: {len(all_episodes)} episodes")
    print(f"❌ Failed to parse: {len(failed)} episodes")
    print(f"💾 Saved to: {output_file}")
    print()
    
    if failed:
        print("Failed episodes:")
        for f in failed[:5]:
            print(f"  - {f}")
        if len(failed) > 5:
            print(f"  ... and {len(failed) - 5} more")
        print()
    
    # Statistics
    total_chars = sum(ep['transcript_length'] for ep in all_episodes)
    total_turns = sum(ep['num_turns'] for ep in all_episodes)
    avg_turns = total_turns / len(all_episodes) if all_episodes else 0
    
    print("📈 STATISTICS:")
    print("-" * 60)
    print(f"  Total characters: {total_chars:,}")
    print(f"  Average per episode: {total_chars // len(all_episodes):,} chars")
    print(f"  Total speaker turns: {total_turns:,}")
    print(f"  Average turns per episode: {avg_turns:.1f}")
    print()
    
    # Show sample episodes
    print("📝 SAMPLE EPISODES:")
    print("-" * 60)
    for ep in all_episodes[:3]:
        print(f"  • {ep['guest']}: {ep['title'][:60]}...")
        print(f"    Turns: {ep['num_turns']}, Length: {ep['transcript_length']:,} chars")
    
    print()
    print("=" * 60)
    print("✅ ALL EPISODES PARSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    process_all_episodes()
