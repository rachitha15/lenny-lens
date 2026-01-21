"""
Generate Episode Action Guides using GPT
Uses real episode data from chunks table
"""

import psycopg2
import requests
import json
import time
import os
from dotenv import load_dotenv
import hashlib

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
NEON_DB_URL = os.getenv('DATABASE_URL')

def get_db():
    return psycopg2.connect(NEON_DB_URL)

def call_gpt(prompt, max_tokens=1200):
    """Call GPT for guide generation"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, verify=False, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ GPT Error: {e}")
        return None

def get_unique_episodes():
    """Get all unique episodes from chunks table"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            episode_guest,
            episode_title,
            STRING_AGG(text, ' ' ORDER BY id) as combined_text,
            COUNT(*) as chunk_count
        FROM chunks
        GROUP BY episode_guest, episode_title
        ORDER BY COUNT(*) DESC
    """)
    
    episodes = cur.fetchall()
    cur.close()
    conn.close()
    
    return episodes

def generate_action_guide(guest, title, content):
    """Generate action guide for one episode"""
    
    # Truncate content to fit in GPT context
    content_sample = content[:12000]
    
    prompt = f"""Analyze this podcast episode and create an ACTIONABLE guide.

Guest: {guest}
Episode: {title}

Content:
{content_sample}

Generate a JSON response with these fields:

{{
  "tldr": "One compelling sentence summarizing the core insight (max 150 chars)",
  "key_frameworks": ["Framework 1", "Framework 2", "Framework 3"],
  "action_items": [
    "Concrete action 1 (specific, starts with verb)",
    "Concrete action 2",
    ... (6-12 items)
  ],
  "when_applies": [
    "✅ Scenario 1 when this advice applies",
    "✅ Scenario 2",
    ... (4-6 scenarios)
  ],
  "listen_if": "One sentence: who should listen to this episode",
  "skip_if": "One sentence: who can skip this episode"
}}

REQUIREMENTS:
- TL;DR must be punchy and compelling (not generic)
- Frameworks: Only include if explicitly mentioned by name
- Action items: SPECIFIC, ACTIONABLE (not "think about X" but "do Y")
- When applies: Concrete scenarios (role, stage, situation)
- Keep it practical and specific

JSON:"""
    
    result = call_gpt(prompt, max_tokens=1200)
    
    if result:
        try:
            # Clean markdown fences if present
            clean = result.strip()
            if clean.startswith('```json'):
                clean = clean[7:]
            if clean.endswith('```'):
                clean = clean[:-3]
            
            guide = json.loads(clean.strip())
            return guide
        except Exception as e:
            print(f"⚠️  Parse error: {e}")
            return None
    
    return None

def save_guide(guest, title, guide):
    """Save guide to database"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO episode_guides 
            (episode_guest, episode_title, tldr, key_frameworks, action_items, when_applies, listen_if, skip_if)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (episode_guest, episode_title) DO UPDATE
            SET tldr = EXCLUDED.tldr,
                key_frameworks = EXCLUDED.key_frameworks,
                action_items = EXCLUDED.action_items,
                when_applies = EXCLUDED.when_applies,
                listen_if = EXCLUDED.listen_if,
                skip_if = EXCLUDED.skip_if
        """, (
            guest, title,
            guide['tldr'],
            guide['key_frameworks'],
            guide['action_items'],
            guide['when_applies'],
            guide['listen_if'],
            guide['skip_if']
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Save error: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return False

def main():
    print("🚀 Generating Episode Action Guides\n")
    
    # Get all episodes
    print("📊 Loading episodes from database...")
    episodes = get_unique_episodes()
    print(f"✅ Found {len(episodes)} unique episodes\n")
    
    # For testing, start with top 10 episodes
    TEST_MODE = False
    if TEST_MODE:
        episodes = episodes[:10]
        print(f"🧪 TEST MODE: Processing {len(episodes)} episodes\n")
    
    success = 0
    failed = 0
    
    for idx, (guest, title, content, chunk_count) in enumerate(episodes, 1):
        print(f"\n[{idx}/{len(episodes)}] {guest} - {title[:50]}...")
        print(f"   Chunks: {chunk_count}")
        
        # Generate guide
        guide = generate_action_guide(guest, title, content)
        
        if guide:
            # Save to database
            if save_guide(guest, title, guide):
                print(f"   ✅ Guide created!")
                print(f"      TL;DR: {guide['tldr'][:80]}...")
                print(f"      Frameworks: {len(guide['key_frameworks'])}")
                print(f"      Actions: {len(guide['action_items'])}")
                success += 1
            else:
                print(f"   ❌ Failed to save")
                failed += 1
        else:
            print(f"   ❌ Failed to generate")
            failed += 1
        
        # Rate limiting
        time.sleep(2)
    
    print(f"\n" + "="*60)
    print(f"📊 SUMMARY")
    print(f"="*60)
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    print(f"💾 Saved to episode_guides table in Neon")
    
    if TEST_MODE:
        print(f"\n🧪 TEST COMPLETE!")
        print(f"To process all {len(get_unique_episodes())} episodes:")
        print(f"   Edit script: TEST_MODE = False")
        print(f"   Cost: ~$3-5 for all episodes")
        print(f"   Time: ~2-3 hours")

if __name__ == "__main__":
    main()
