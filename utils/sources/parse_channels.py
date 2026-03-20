import json
import re

def parse_channels(input_file, output_file):
    """
    Parse channels.txt into a JSON array.
    Format: 
    <tv_channel_name>
    <search_query>
    <yt_channel_url> - <yt_channel_id>
    """
    channels = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by double newlines to get each channel block
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
        
        if len(lines) < 3:
            continue
            
        tv_channel_name = lines[0]
        search_query = lines[1]
        
        # Process all YouTube channel URLs (some channels have multiple)
        for i in range(2, len(lines)):
            url_line = lines[i]
            
            # Parse the URL and ID
            if ' - ' in url_line:
                parts = url_line.split(' - ')
                yt_channel_url = parts[0].strip()
                yt_channel_id = parts[1].strip()
                
                channel_entry = {
                    "tv_channel_name": tv_channel_name,
                    "search_query": search_query,
                    "yt_channel_url": yt_channel_url,
                    "yt_channel_id": yt_channel_id
                }
                
                channels.append(channel_entry)
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)
    
    print(f"Successfully parsed {len(channels)} channel entries.")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    parse_channels('channels.txt', 'channels.json')
