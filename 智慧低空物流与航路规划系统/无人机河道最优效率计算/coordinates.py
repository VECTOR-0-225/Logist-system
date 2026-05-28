# -*- coding: utf-8 -*-
"""
📌 资产供应端：高德多品牌地毯式抓取与自动入库系统
功能：根据用户输入的品牌，自动翻页抓取 5 公里内全量坐标
"""
import urllib.parse
import requests
import sqlite3
import os

# ==========================================
# 基础配置参数
# ==========================================
AMAP_KEY = '39e208883246d56171b70ffdd4fb7cb7'  # 你的高德 Web服务 Key
CENTER_COORDINATE = '120.16708,30.294078'     # 你的中心点坐标
RADIUS = 5000                                 # 搜索半径：5000米（5公里）
DB_PATH = 'uav_logistic_system.db'            # 统一的数据库文件名

# ==========================================
# 🗄️ 数据库自动初始化芯片
# ==========================================
def init_database():
    """确保本地 SQLite 数据库及三张核心资产表完好无损"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 建立商家表（如果不存在的话）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS merchants (
            name TEXT PRIMARY KEY, lat REAL, lng REAL, river TEXT
        )''')
    # 顺便建立接力柜和校园柜空表，防止画图脚本因为表不存在而闪退
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relay_hubs (
            name TEXT PRIMARY KEY, lat REAL, lng REAL, river TEXT
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campus_hubs (
            name TEXT PRIMARY KEY, lat REAL, lng REAL
        )''')
    conn.commit()
    conn.close()

# 初始化数据库
init_database()

print("==================================================")
print("🎉 欢迎使用无人机配送商户坐标【SQLite 自动同步版】系统")
print("👉 提示：请输入想查询的多个品牌，用【逗号】隔开。")
print("👉 示例：麦当劳, 喜茶, 肯德基, 瑞幸咖啡")
print("👉 提示：输入 'exit' 可结束程序。")
print("==================================================")

while True:
    # 1. 获取用户输入的原始字符串
    raw_input = input("\n请输入商户名称（逗号隔开）: ").strip()
    
    if raw_input.lower() in ['exit', '退出', 'q']:
        print("👋 坐标抓取程序已退出。数据库资产已安全锁定！")
        break
        
    if not raw_input:
        print("⚠️ 输入不能为空，请重新输入。")
        continue

    # 2. 兼容中文和英文逗号
    keywords_list = [kw.strip() for kw in raw_input.replace('，', ',').split(',') if kw.strip()]
    
    if not keywords_list:
        print("⚠️ 未解析出有效的关键词，请重新输入。")
        continue

    print(f"🚀 开始地毯式搜索半径 {RADIUS} 米（5公里）内的目标商户...")
    
    # 建立一个总字典，用来存放所有品类的去重结果
    ALL_MERCHANTS_RESULTS = {}

    # 3. 遍历每一个关键词进行抓取
    for user_keyword in keywords_list:
        print(f" └─ 正在抓取 '{user_keyword}'...")
        page = 1
        
        while True:
            # 安全 URL 编码
            encoded_keyword = urllib.parse.quote(user_keyword)
            url = f"https://restapi.amap.com/v3/place/around?key={AMAP_KEY}&location={CENTER_COORDINATE}&keywords={encoded_keyword}&radius={RADIUS}&offset=20&page={page}&extensions=base"
            
            try:
                response = requests.get(url, timeout=10)
                data = response.json()
                
                if data['status'] == '1':
                    pois = data.get('pois', [])
                    if not pois:  # 没数据了，该词抓完
                        break
                    
                    for poi in pois:
                        name = poi['name']
                        location_str = poi['location']
                        
                        # 高德返回的是 "经度,纬度"
                        lon_str, lat_str = location_str.split(',')
                        
                        # ✨ 核心绑定：在入库前，自动通过名字分析该商家属于哪个水系网络（用于后端的图论和弹窗显示）
                        detected_river = "未知水系"
                        if "运河" in name or "乐堤港" in name or "大悦城" in name or "水晶城" in name:
                            detected_river = "京杭大运河"
                        elif "工大" in name or "德胜" in name or "和平" in name:
                            detected_river = "上塘河"
                        elif "武林" in name or "国大" in name or "嘉里" in name or "凤起" in name:
                            detected_river = "中河"
                        elif "黄龙" in name or "文三" in name or "古翠" in name:
                            detected_river = "沿山河"
                        elif "三里亭" in name:
                            detected_river = "麦庙港"
                            
                        # 格式化为：[纬度, 经度, 绑定河流]
                        ALL_MERCHANTS_RESULTS[name] = [float(lat_str), float(lon_str), detected_river]
                    
                    page += 1
                else:
                    print(f"    ❌ 高德接口报错: {data.get('info')}")
                    break
            except Exception as e:
                print(f"    ❌ 网络请求失败: {e}")
                break

    # ==========================================
    # 💾 4. 全自动入库写入引擎（用数据替换打印代码）
    # ==========================================
    if ALL_MERCHANTS_RESULTS:
        print(f"\n✅ 批量抓取成功！方圆 5 公里内共获得 {len(ALL_MERCHANTS_RESULTS)} 家商户。")
        print("🗄️  正在将新抓取的商户坐标无缝更新至本地 SQLite 数据库...")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 为了保持数据纯净度，先清空旧的商家历史缓存
            cursor.execute("DELETE FROM merchants")
            
            # 构建批量插入的结构
            insert_rows = []
            for name, info in ALL_MERCHANTS_RESULTS.items():
                insert_rows.append((name, info[0], info[1], info[2]))
                
            # 执行工业级高速批量替换插入 (INSERT OR REPLACE)
            cursor.executemany("INSERT OR REPLACE INTO merchants VALUES (?, ?, ?, ?)", insert_rows)
            
            conn.commit()
            conn.close()
            
            print("--------------------------------------------------")
            print("✨ 【数据链闭合成功】！")
            print(f"🎉 成功向 '{DB_PATH}' 数据库中写入/更新了 {len(insert_rows)} 条商户坐标记录。")
            print("💡 现在你不需要复制任何代码了，直接去运行你的画图大屏程序")
            print("💡 画图程序会自动从库里提取这批全新数据并渲染出带有流光的沿河航线！")
            print("--------------------------------------------------")
            
        except Exception as db_err:
            print(f"❌ 数据库写入失败: {db_err}")
    else:
        print("⚠️ 方圆 5 公里内没有搜到任何相关商户，数据库未作变更。")