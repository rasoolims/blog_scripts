import requests
import argparse
import sys

def fetch_all_snapshot_ids(target_url, output_file):
    # The CDX API endpoint for listing snapshots
    # 'output=json' and 'fl=timestamp' ensures we only get the IDs
    cdx_url = f"http://web.archive.org/cdx/search/cdx?url={target_url}&output=json&fl=timestamp&filter=statuscode:200"
    
    print(f"📡 Fetching snapshot IDs for: {target_url}")
    
    try:
        response = requests.get(cdx_url, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # The first row is the header ['timestamp'], so we skip it
        if len(data) > 1:
            snapshot_ids = [row[0] for row in data[1:]]
            # Remove duplicates (in case of multiple captures per second)
            unique_ids = sorted(list(set(snapshot_ids)))
            
            with open(output_file, "w", encoding="utf-8") as f:
                for ts in unique_ids:
                    f.write(f"{ts}\n")
            
            print(f"✅ Success! Saved {len(unique_ids)} snapshot IDs to: {output_file}")
        else:
            print("⚠️ No snapshots found for this URL.")
            
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch all snapshot IDs for a given URL.")
    parser.add_argument("--url", default="delsharm.blogfa.com", help="The blog URL to scan")
    parser.add_argument("--output", default="snapshot_ids.txt", help="Output file path")
    
    args = parser.parse_args()
    fetch_all_snapshot_ids(args.url, args.output)