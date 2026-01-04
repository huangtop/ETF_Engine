import sys
sys.path.insert(0, '.')
from font_config import setup_chinese_font_enhanced, update_font_sizes, FONT_SIZE_CONFIG
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

print('Running local font smoke test')
setup_chinese_font_enhanced()
update_font_sizes()

# print available fonts that match Chinese candidates
candidates = ['SimHei', 'STHeiti', 'NotoSansCJK', 'Noto Sans CJK', 'DejaVu Sans', 'Liberation Sans']
found = []
for f in fm.findSystemFonts(fontpaths=None, fontext='ttf'):
    for c in candidates:
        if c.lower() in os.path.basename(f).lower():
            found.append(f)

print('Found candidate font paths (sample):')
for p in found[:5]:
    print(' ', p)

# create a simple PNG with Chinese text
fig, ax = plt.subplots(figsize=(6,2))
ax.text(0.5, 0.5, '測試中文顯示：台灣 ETF 測試', ha='center', va='center', fontsize=16)
ax.axis('off')

out = 'charts_output/font_smoke_test.png'
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.close()
print('Saved sample image to', out)
