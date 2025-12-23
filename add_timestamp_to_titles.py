#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在所有图表标题中添加时间戳
"""
import re
from datetime import datetime

def add_timestamps_to_radar_chart(filepath):
    """在雷达图标题中添加时间戳"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 获取当前时间
    current_time = datetime.now().strftime('%Y%m%d %H:%M')
    
    # 替换雷达图标题（第一个set_title）
    # 从 '台股股票型ETF雷達圖\n● 圓形標記' 改为 '台股股票型ETF雷達圖\n● 圓形標記 {time}生成'
    
    # 使用更精确的替换
    patterns = [
        (r"ax\.set_title\(title, fontsize=18", f"ax.set_title(title + f' {current_time}生成', fontsize=18"),
        (r"ax\.set_title\(title, fontsize=20", f"ax.set_title(title + f' {current_time}生成', fontsize=20"),
        (r"ax\.set_title\('ETF多指標性能比較表", f"ax.set_title(f'ETF多指標性能比較表 {current_time}生成'"),
        (r"plt\.title\('ETF多指標", f"plt.title(f'ETF多指標性能比較表 {current_time}生成'"),
    ]
    
    for pattern, replacement in patterns:
        if pattern in content:
            content = re.sub(pattern, replacement, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 已添加时间戳到标题")

if __name__ == '__main__':
    add_timestamps_to_radar_chart('ETFEngine_main.py')
