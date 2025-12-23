#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
為所有生成的 PNG 圖表添加時間戳
在圖表右下角添加"Generated: YYYY-MM-DD HH:MM:SS"文字
"""

import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

def add_timestamp_to_image(image_path, timestamp=None):
    """為圖片添加時間戳"""
    if timestamp is None:
        # 使用文件修改時間
        timestamp = datetime.fromtimestamp(os.path.getmtime(image_path))
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    else:
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # 打開圖片
        img = Image.open(image_path)
        
        # 創建繪圖對象
        draw = ImageDraw.Draw(img)
        
        # 嘗試使用系統字體，如果失敗使用默認字體
        try:
            # macOS 字體路徑
            font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 10)
        except:
            try:
                # Linux 字體路徑
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except:
                # 使用默認字體
                font = ImageFont.load_default()
        
        # 在右下角添加時間戳
        text = f"Generated: {timestamp_str}"
        
        # 獲取文本大小
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 設置位置（右下角，距離邊緣 10 像素）
        x = img.width - text_width - 10
        y = img.height - text_height - 10
        
        # 添加半透明背景
        padding = 5
        background_box = [x - padding, y - padding, 
                         x + text_width + padding, y + text_height + padding]
        
        # 創建新圖層用於半透明背景
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(background_box, fill=(255, 255, 255, 200))
        
        # 合併層
        if img.mode == 'RGB':
            img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        
        # 在背景上繪製文本
        draw = ImageDraw.Draw(img)
        draw.text((x, y), text, fill=(100, 100, 100), font=font)
        
        # 保存圖片
        img.save(image_path, 'PNG')
        return True
        
    except Exception as e:
        print(f"  ⚠️  添加時間戳失敗 {os.path.basename(image_path)}: {e}")
        return False


def process_output_folder(folder_path):
    """處理輸出文件夾中的所有 PNG 文件"""
    if not os.path.exists(folder_path):
        print(f"❌ 文件夾不存在: {folder_path}")
        return
    
    png_files = [f for f in os.listdir(folder_path) if f.endswith('.png')]
    
    if not png_files:
        print(f"⚠️  文件夾中沒有 PNG 文件: {folder_path}")
        return
    
    print(f"\n📌 為 {len(png_files)} 個 PNG 文件添加時間戳...\n")
    
    success_count = 0
    for filename in png_files:
        image_path = os.path.join(folder_path, filename)
        if add_timestamp_to_image(image_path):
            print(f"  ✅ {filename}")
            success_count += 1
        else:
            print(f"  ❌ {filename}")
    
    print(f"\n✅ 完成: {success_count}/{len(png_files)} 個文件成功添加時間戳")


def process_all_output_folders():
    """處理所有輸出文件夾"""
    output_folders = [
        'Output_Active_ETF',
        'Output_HighDividend_ETF',
        'Output_Industry_ETF',
        'Output_US_ETF',
        'Output_Dividend_ETF',
        'Output_Default'
    ]
    
    for folder in output_folders:
        if os.path.exists(folder):
            print(f"\n{'='*60}")
            print(f"處理文件夾: {folder}")
            print(f"{'='*60}")
            process_output_folder(folder)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # 處理指定文件夾
        folder = sys.argv[1]
        process_output_folder(folder)
    else:
        # 處理所有文件夾
        process_all_output_folders()
    
    print("\n" + "="*60)
    print("所有 PNG 文件已添加時間戳 ✅")
    print("="*60)
