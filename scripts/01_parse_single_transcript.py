"""
Parse a single transcript file to understand its structure.
This helps us test our parsing logic before running on all 303 episodes.
"""

import yaml
import os
from pathlib import Path

def parse_transcript(file_path):
    """Parse a single transcript markdown file"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split YAML frontmatter from content
    # Format: ---\nYAML\n---\nContent
    parts = content.split('---')
    
    if len(parts) < 3:
        print(f"⚠️ Warning: File doesn't have proper YAML frontmatter")
        return None
    
    # Extract YAML metadata (part between first two ---)
    frontmatter_text = parts[1]
    transcript_text = '---'.join(parts[2:])  # Everything after second ---
    
    # Parse YAML
    try:
        metadata = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML: {e}")
        return None
    
    # Extract guest name from folder structure
    # Path format: .../episodes/guest-name/transcript.md
    guest_folder = Path(file_path).parent.name
    
    return {
        'guest_folder': guest_folder,
        'metadata': metadata,
        'transcript_text': transcript_text.strip(),
        'transcript_length': len(transcript_text.strip()),
        'file_path': file_path
    }

def extract_speaker_turns(transcript_text):
    """Extract individual speaker turns from transcript"""
    
    lines = transcript_text.split('\n')
    turns = []
    current_speaker = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and markdown headers
        if not line or line.startswith('#'):
            continue
        
        # Check if line starts with a speaker (contains timestamp in parentheses)
        # Format: "Speaker Name (00:00:00):"
        if '(' in line and '):' in line:
            # Save previous turn
            if current_speaker and current_text:
                turns.append({
                    'speaker': current_speaker,
                    'text': ' '.join(current_text).strip()
                })
            
            # Extract new speaker and timestamp
            speaker_part = line.split('(')[0].strip()
            timestamp_and_text = line.split('):')
            
            if len(timestamp_and_text) > 1:
                current_speaker = speaker_part
                current_text = [timestamp_and_text[1].strip()]
            else:
                current_text.append(line)
        else:
            # Continue current speaker's text
            if current_speaker:
                current_text.append(line)
    
    # Add last turn
    if current_speaker and current_text:
        turns.append({
            'speaker': current_speaker,
            'text': ' '.join(current_text).strip()
        })
    
    return turns

if __name__ == "__main__":
    # Test with Ada Chen Rekhi's transcript
    test_file = "data/lennys-podcast-transcripts/episodes/brian-chesky/transcript.md"
    
    print("=" * 60)
    print("📄 PARSING SINGLE TRANSCRIPT TEST")
    print("=" * 60)
    print()
    
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        print("Available episodes:")
        episodes_dir = "data/lennys-podcast-transcripts/episodes"
        for folder in sorted(os.listdir(episodes_dir))[:5]:
            print(f"  - {folder}")
        exit(1)
    
    # Parse the transcript
    print(f"Parsing: {test_file}")
    print()
    
    result = parse_transcript(test_file)
    
    if result:
        print("✅ Successfully parsed!")
        print()
        print("📊 METADATA:")
        print("-" * 60)
        for key, value in result['metadata'].items():
            if isinstance(value, list):
                print(f"  {key}: {', '.join(map(str, value[:3]))}{'...' if len(value) > 3 else ''}")
            else:
                value_str = str(value)[:100]
                print(f"  {key}: {value_str}")
        print()
        
        print("📝 TRANSCRIPT INFO:")
        print("-" * 60)
        print(f"  Guest folder: {result['guest_folder']}")
        print(f"  Transcript length: {result['transcript_length']:,} characters")
        print(f"  First 200 chars: {result['transcript_text'][:200]}...")
        print()
        
        # Extract speaker turns
        print("🎙️ EXTRACTING SPEAKER TURNS:")
        print("-" * 60)
        turns = extract_speaker_turns(result['transcript_text'])
        print(f"  Total turns: {len(turns)}")
        
        if len(turns) > 0:
            print()
            print("  First 3 turns:")
            for i, turn in enumerate(turns[:3]):
                print(f"\n  Turn {i+1}:")
                print(f"    Speaker: {turn['speaker']}")
                text_preview = turn['text'][:150] + "..." if len(turn['text']) > 150 else turn['text']
                print(f"    Text: {text_preview}")
        
        print()
        print("=" * 60)
        print("✅ TEST COMPLETE!")
        print("=" * 60)
    else:
        print("❌ Failed to parse transcript")
