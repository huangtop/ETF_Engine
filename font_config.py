# 字体配置模块
# 解决中文显示和字体大小问题

import matplotlib.pyplot as plt
import matplotlib
from matplotlib import font_manager as fm
import os

def setup_chinese_font_enhanced():
    """
    改进的中文字体设置
    支持macOS、Windows、Linux系统
    """
    # 首先尝试使用系统中文字体
    system = matplotlib.rcParams['figure.figsize']
    
    font_candidates = [
        '/Library/Fonts/SimHei.ttf',      # macOS - Microsoft SimHei
        '/Library/Fonts/STHeiti Medium.ttc',  # macOS - STHeiti
        '/System/Library/Fonts/STHeiti.ttc',  # macOS - STHeiti
        'C:\\Windows\\Fonts\\SimHei.ttf', # Windows
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf',  # Linux
    ]
    
    # 尝试查找可用字体
    font_path = None
    for candidate in font_candidates:
        if os.path.exists(candidate):
            font_path = candidate
            break
    
    # 如果没找到，使用系统默认中文字体列表
    if font_path:
        prop = fm.FontProperties(fname=font_path)
        matplotlib.rcParams['font.sans-serif'] = [prop.get_name()]
    else:
        # 使用备选字体列表
        font_list = [
            'STHeiti',           # macOS
            'SimHei',            # Windows/Linux
            'DejaVu Sans',       # 备选
            'Liberation Sans',
        ]
        matplotlib.rcParams['font.sans-serif'] = font_list
    
    # 其他配置
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 11  # 基础字体大小

# 字体大小配置
FONT_SIZE_CONFIG = {
    'title_large': 27,        # 大标题: 18 * 1.5
    'title_medium': 21,       # 中标题: 14 * 1.5
    'title_small': 18,        # 小标题: 12 * 1.5
    
    'label_large': 18,        # 大标签: 12 * 1.5
    'label_medium': 15,       # 中标签: 10 * 1.5
    'label_small': 13,        # 小标签: 8.5 * 1.5
    
    'tick_large': 16,         # 大刻度: ~10.5 * 1.5
    'tick_medium': 13,        # 中刻度: ~8.5 * 1.5
    'tick_small': 11,         # 小刻度: 7.5 * 1.5
    
    'legend': 26,             # 图例: 13 * 2（加大一倍）
    'legend_title': 30,       # 图例标题: 15 * 2（加大一倍）
    
    'text_annotation': 14,    # 注释文本: ~9 * 1.5
    'figure_text': 12,        # 图形文本: 8 * 1.5
}

# 颜色配置
COLOR_CONFIG = {
    'active_etf_main': '#FF6384',      # 主动型ETF - 红粉
    'passive_etf': '#36A2EB',          # 被动型ETF - 蓝色
    'us_etf': '#FF9F40',               # 美股ETF - 橙色
    'benchmark': '#D3D3D3',            # 基准 - 灰色
    'grid': '#CCCCCC',                 # 网格 - 浅灰
}

def update_font_sizes():
    """更新matplotlib默认字体大小"""
    plt.rcParams.update({
        'font.size': FONT_SIZE_CONFIG['label_medium'],
        'axes.labelsize': FONT_SIZE_CONFIG['label_large'],
        'axes.titlesize': FONT_SIZE_CONFIG['title_medium'],
        'xtick.labelsize': FONT_SIZE_CONFIG['tick_medium'],
        'ytick.labelsize': FONT_SIZE_CONFIG['tick_medium'],
        'legend.fontsize': FONT_SIZE_CONFIG['legend'],
        'figure.titlesize': FONT_SIZE_CONFIG['title_large'],
    })
