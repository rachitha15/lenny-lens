import os
"""
Extract frameworks and mental models from podcast episodes using AI
"""

import psycopg2
import requests
import json
from collections import defaultdict
import time

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_db():
    return psycopg2.connect(
        dbname="lenny_knowledge",
        user="rachitha.suresh",
        host="localhost"
    )

def call_gpt(prompt, max_tokens=1000):
    """Call GPT for analysis"""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3  # Lower temp for consistency
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, verify=False, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"GPT Error: {e}")
        return None

def extract_frameworks_from_sample():
    """Step 1: Identify frameworks from a sample of episodes"""
    
    print("📊 Sampling episodes to identify frameworks...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get diverse sample: top guests with most content
    cur.execute("""
        SELECT episode_guest, episode_title, 
               STRING_AGG(text, ' ' ORDER BY id) as combined_text
        FROM chunks
        WHERE chunk_type = 'qa_pair'
        GROUP BY episode_guest, episode_title
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    
    episodes = cur.fetchall()
    
    print(f"✅ Sampled {len(episodes)} episodes")
    
    # Analyze episodes to find frameworks
    all_frameworks = set()
    
    for idx, (guest, title, text) in enumerate(episodes):
        print(f"\n🔍 Analyzing {idx+1}/20: {guest} - {title[:50]}...")
        
        # Truncate text to avoid token limits
        sample_text = text[:4000]
        
        prompt = f"""Analyze this podcast episode excerpt and identify any frameworks, mental models, methodologies, or specific approaches mentioned.

Guest: {guest}
Episode: {title}

Excerpt:
{sample_text}

Identify:
1. Named frameworks (e.g., "RICE Framework", "Jobs-to-be-Done", "OKRs")
2. Mental models (e.g., "Founder Mode", "Add a Zero Thinking")
3. Guest-specific approaches (e.g., "11-Star Experience", "LNO Framework")
4. Methodologies (e.g., "Continuous Discovery", "Design Sprints")

For each one found, respond ONLY with a JSON array like:
[
  {{
    "name": "Framework Name",
    "type": "framework|mental_model|guest_approach|methodology",
    "brief_description": "One sentence what it is",
    "mentioned_by": "{guest}"
  }}
]

If NO frameworks are found, return: []

JSON response:"""
        
        result = call_gpt(prompt, max_tokens=800)
        
        if result:
            try:
                # Parse JSON
                frameworks = json.loads(result)
                for fw in frameworks:
                    all_frameworks.add((
                        fw['name'],
                        fw['type'],
                        fw['brief_description']
                    ))
                print(f"   Found {len(frameworks)} frameworks")
            except:
                print(f"   ⚠️  Failed to parse JSON")
        
        time.sleep(1)  # Rate limiting
    
    cur.close()
    conn.close()
    
    print(f"\n✅ Total unique frameworks identified: {len(all_frameworks)}")
    
    # Save to file
    frameworks_list = [
        {"name": name, "type": ftype, "description": desc}
        for name, ftype, desc in sorted(all_frameworks)
    ]
    
    with open('data/identified_frameworks.json', 'w') as f:
        json.dump(frameworks_list, f, indent=2)
    
    print(f"✅ Saved to data/identified_frameworks.json")
    return frameworks_list

if __name__ == "__main__":
    print("🚀 Starting framework extraction...\n")
    frameworks = extract_frameworks_from_sample()
    print(f"\n✨ Extraction complete! Found {len(frameworks)} frameworks")
    print("\nTop 10 frameworks:")
    for fw in frameworks[:10]:
        print(f"  • {fw['name']} ({fw['type']})")
