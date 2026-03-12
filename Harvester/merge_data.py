import os
import shutil
import sys

src = r"c:\Users\marek\.gemini\antigravity\scratch\data"
dst = r"c:\Users\marek\.gemini\antigravity\scratch\tick scraper\data"

if not os.path.exists(src):
    print("Src doesn't exist.")
    sys.exit(0)

for root, dirs, files in os.walk(src):
    for file in files:
        src_file = os.path.join(root, file)
        rel_path = os.path.relpath(src_file, src)
        dst_file = os.path.join(dst, rel_path)
        
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        # If it doesn't exist in dst, move it
        if not os.path.exists(dst_file):
            shutil.move(src_file, dst_file)
            print(f"Moved {rel_path}")
        else:
            # If it does exist append
            with open(src_file, 'rb') as f_src, open(dst_file, 'ab') as f_dst:
                f_dst.write(f_src.read())
            os.remove(src_file)
            print(f"Appended {rel_path}")

shutil.rmtree(src)
print("Done merging.")
