#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from datetime import datetime

def add_timestamps_to_all_charts(filepath):
    """在所有圖表標題中添加中文標題和時間戳（簡化版本）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 獲取當前時間
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    timestamp_suffix = f' ({current_time}生成)'
    
    # 檢查是否已經有時間戳，避免重複添加
    if re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}生成', content):
        print("⚠️  圖表標題已包含時間戳")
        return False
    
    modified = False
    
    # 1. 處理 ax.set_title(title, ...) 格式
    pattern1 = r'\.set_title\(title,'
    if re.search(pattern1, content):
        content = re.sub(pattern1, f'.set_title(title + "{timestamp_suffix}",', content)
        modified = True
        print("✅ 添加時間戳到變數標題 (set_title)")
    
    # 2. 處理 plt.title(title, ...) 格式
    pattern2 = r'plt\.title\(title,'
    if re.search(pattern2, content):
        content = re.sub(pattern2, f'plt.title(title + "{timestamp_suffix}",', content)
        modified = True
        print("✅ 添加時間戳到變數標題 (plt.title)")
    
    # 3. 處理固定字符串標題 ax.set_title('固定標題', ...)
    def replace_fixed_title(match):
        title = match.group(1)
        return f".set_title('{title}{timestamp_suffix}',"
    
    pattern3 = r"\.set_title\('([^']+)',"
    if re.search(pattern3, content):
        content = re.sub(pattern3, replace_fixed_title, content)
        modified = True
        print("✅ 添加時間戳到固定標題 (set_title)")
    
    # 4. 處理固定字符串標題 plt.title('固定標題', ...)
    def replace_fixed_plt_title(match):
        title = match.group(1)
        return f"plt.title('{title}{timestamp_suffix}',"
    
    pattern4 = r"plt\.title\('([^']+)',"
    if re.search(pattern4, content):
        content = re.sub(pattern4, replace_fixed_plt_title, content)
        modified = True
        print("✅ 添加時間戳到固定標題 (plt.title)")
    
    # 保存修改後的內容
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已為所有圖表標題添加時間戳: {current_time}")
        return True
    else:
        print("⚠️  未找到需要添加時間戳的標題")
        return False
        print("⚠️  未找到需要替換的標題")

if __name__ == '__main__':
    add_timestamps_to_all_charts('generate_all_charts.py')
