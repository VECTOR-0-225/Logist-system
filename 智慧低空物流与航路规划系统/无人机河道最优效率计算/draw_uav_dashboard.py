# -*- coding: utf-8 -*-
"""
📌 数字大屏生成中心
功能：修复静默退出Bug。动态读取 SQLite 数据库商户，自动兼容缺少的预设接力柜，
      穿透 GeoJSON 构建水系轨道，调用 Dijkstra 算法生成完美贴合河流的动态流光大屏。
"""
import os
import math
import json
import sqlite3

try:
    import networkx as nx
    import folium
    from folium.plugins import AntPath
except ImportError:
    print("❌ 错误：缺少必要的库！请在终端执行: pip install folium networkx")
    exit(1)

MAP_CENTER = [30.294724, 120.166277]

# =========================================================================
# 🔌 第一部分：智能数据读取中心（带空表兜底保护机制）
# =========================================================================
def load_assets_from_db():
    # 兜底预设：万一数据库里没存柜子，就用这套标准的柜子体系
    fallback_campus = {
        "浙工大北门终端柜": [30.295476, 120.166426],
        "浙工大东门终端柜": [30.294561, 120.166601],
        "浙工大南门终端柜": [30.294135, 120.165826]
    }
    fallback_relays = {
        "智能接力柜 #1": [30.261334, 120.171748, "中河"],
        "智能接力柜 #2": [30.281245, 120.160482, "京杭大运河"],
        "智能接力柜 #3": [30.314175, 120.149522, "姚家坝河"],
        "智能接力柜 #4": [30.270204, 120.128182, "沿山河"],
        "智能接力柜 #5": [30.298960, 120.165412, "上塘河"],
        "智能接力柜 #6": [30.293656, 120.201323, "东新河"],
        "智能接力柜 #7": [30.292637, 120.135165, "余杭塘河"],
        "智能接力柜 #8": [30.318797, 120.183257, "西湖漾"],
        "智能接力柜 #9": [30.300744, 120.210574, "弄口港"],
        "智能接力柜 #10": [30.276799,120.185019, "京杭大运河"],
        "智能接力柜 #11": [30.309256, 120.133914, "西塘河"],
        "智能接力柜 #12": [30.276486, 120.154230, "古新河"],
        "智能接力柜 #13": [30.327571, 120.159131, "热水河"],
        "智能接力柜 #14": [30.258222,120.179489, "东河"],
        "智能接力柜 #15": [30.293895, 120.124463, "余杭塘河"],
        "智能接力柜 #16": [30.254459,120.171805, "中河"],
        "智能接力柜 #17": [30.272976, 120.218269, "京杭大运河"],
        "智能接力柜 #18": [30.329346, 120.191613, "凤水墩"],
        "智能接力柜 #19": [30.306049, 120.159152, "上塘河"],
        "智能接力柜 #20": [30.314083, 120.127172, "西塘河"],
        "智能接力柜 #21": [30.326012, 120.149204, "红建河"],
        "智能接力柜 #22": [30.299112, 120.191896, "东新河"],
        "智能接力柜 #23": [30.282422, 120.207487, "备塘河"],
        "智能接力柜 #24": [30.271001, 120.123610, "沿山河"],
    }
    merchants = {}

    if not os.path.exists('uav_logistic_system.db'):
        print("⚠️ 警告：未发现数据库，自动使用纯预设模式启动...")
        return fallback_campus, fallback_relays, merchants
        
    conn = sqlite3.connect('uav_logistic_system.db')
    cursor = conn.cursor()
    
    # 1. 尝试读取校园柜（如果库里为空，触发兜底）
    try:
        cursor.execute("SELECT name, lat, lng FROM campus_hubs")
        rows = cursor.fetchall()
        campus_hubs = {row[0]: [row[1], row[2]] for row in rows} if rows else fallback_campus
    except: campus_hubs = fallback_campus
    
    # 2. 尝试读取接力柜（如果库里为空，触发兜底）
    try:
        cursor.execute("SELECT name, lat, lng, river FROM relay_hubs")
        rows = cursor.fetchall()
        relay_hubs = {row[0]: [row[1], row[2], row[3]] for row in rows} if rows else fallback_relays
    except: relay_hubs = fallback_relays
    
    # 3. 必须读取你辛苦抓取的商家表
    try:
        cursor.execute("SELECT name, lat, lng, river FROM merchants")
        rows = cursor.fetchall()
        merchants = {row[0]: [row[1], row[2], row[3]] for row in rows} if rows else {}
    except: pass
    
    conn.close()
    return campus_hubs, relay_hubs, merchants

# =========================================================================
# ⛓️ 第二部分：图论拓扑算法基础工具
# =========================================================================
def wgs84_to_gcj02(lng, lat):
    """OSM原始数据纠偏到高德火星坐标系"""
    pi = 3.14159265358979323846
    a = 6378245.0
    ee = 0.00669342162296594323
    def _tl(lng, lat):
        ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
        ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lat * pi) + 40.0 * math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 * math.sin(lat * pi / 30.0)) * 2.0 / 3.0
        return ret
    def _tg(lng, lat):
        ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
        ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lng * pi) + 40.0 * math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 * math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
        return ret
    if (lng < 72.004 or lng > 137.8347) or (lat < 0.8293 or lat > 55.8271): return lng, lat
    dlat = _tl(lng - 105.0, lat - 35.0)
    dlng = _tg(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    return lng + (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi), lat + (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)

def get_haversine_distance(c1, c2):
    """计算两点间物理距离 (公里)"""
    rad_lat1, rad_lon1, rad_lat2, rad_lon2 = map(math.radians, [c1[0], c1[1], c2[0], c2[1]])
    a = math.sin((rad_lat2 - rad_lat1)/2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin((rad_lon2 - rad_lon1)/2)**2
    return 2 * math.asin(math.sqrt(a)) * 6371

# =========================================================================
# 🚆 第三部分：拓扑网络编织与 Dijkstra 沿河寻路
# =========================================================================
def build_routes_from_graph(campus_hubs, relay_hubs):
    G = nx.Graph()
    geojson_path = '/Users/vector/Desktop/code_python/无人机河道最优效率计算/export.geojson'
    
    if not os.path.exists(geojson_path):
        print(f"⚠️ 警告：找不到 '{geojson_path}'，无法生成精准贴河航线！")
        return []
        
    print("🕸️  正在读取 GeoJSON 并转换为高德对齐的图论低空水系轨道...")
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)
    
    # 暴力穿透所有嵌套结构，提取真实的河流网格边界
    for feature in geo_data.get('features', []):
        geometry = feature.get('geometry', {})
        geom_type = geometry.get('type')
        coords = geometry.get('coordinates', [])
        
        segments = []
        if geom_type == 'LineString': segments = [coords]
        elif geom_type in ['MultiLineString', 'Polygon']: segments = coords
        elif geom_type == 'MultiPolygon':
            for poly in coords:
                for ring in poly: segments.append(ring)
                
        for seg in segments:
            corrected_seg = []
            for c in seg:
                if len(c) >= 2:
                    glng, glat = wgs84_to_gcj02(float(c[0]), float(c[1]))
                    corrected_seg.append((glat, glng))
            # 建立连续的河道边缘网格
            for i in range(len(corrected_seg) - 1):
                p1, p2 = corrected_seg[i], corrected_seg[i+1]
                G.add_edge(p1, p2, weight=get_haversine_distance(p1, p2))

    all_nodes = list(G.nodes)
    if not all_nodes: return []
        
    planned_routes = []
    
    print("🛸 启动 Dijkstra 无人机空间图论寻路引擎...")
    # 为每一个接力柜匹配最近的学校柜，并在河道网络中寻路
    for hub_name, hub_info in relay_hubs.items():
        h_coord = (hub_info[0], hub_info[1])
        river_name = hub_info[2]
        
        # 找最近的学校终端柜
        best_locker_name = min(campus_hubs.keys(), key=lambda k: get_haversine_distance(h_coord, campus_hubs[k]))
        l_coord = (campus_hubs[best_locker_name][0], campus_hubs[best_locker_name][1])
        
        # 寻找接力柜和学校在河道网络中的【上下车站点】
        entrance = min(all_nodes, key=lambda n: get_haversine_distance(h_coord, n))
        exit_node = min(all_nodes, key=lambda n: get_haversine_distance(l_coord, n))
        
        try:
            # 召唤 Dijkstra 算法，严格在水系图表中滑行
            shortest = nx.shortest_path(G, source=entrance, target=exit_node, weight='weight')
            # 抽样压缩，防止网页卡顿
            step = max(1, len(shortest) // 20)
            smooth = shortest[::step]
            if exit_node not in smooth: smooth.append(exit_node)
            
            final_path = [[h_coord[0], h_coord[1]]] + [[pt[0], pt[1]] for pt in smooth] + [[l_coord[0], l_coord[1]]]
            planned_routes.append({"path": final_path, "desc": f"从 {hub_name} ({river_name}) ➔ 沿低空水系轨道 ➔ {best_locker_name}"})
        except:
            # 万一图谱断裂的极小概率兜底
            planned_routes.append({"path": [[h_coord[0], h_coord[1]], [l_coord[0], l_coord[1]]], "desc": f"{hub_name} ➔ 空间保障线 ➔ {best_locker_name}"})
            
    return planned_routes

# =========================================================================
# 🎨 第四部分：渲染主程序
# =========================================================================
def main_render():
    print("🚀 启动数据可视化引擎...")
    
    # 1. 智能从数据库抽水
    campus_hubs, relay_hubs, merchants = load_assets_from_db()
    if not campus_hubs: 
        print("❌ 提取失败：请检查数据库结构。")
        return
        
    print(f"📊 资产加载状态：{len(merchants)}家商户 | {len(relay_hubs)}个枢纽柜 | {len(campus_hubs)}个终端柜")
    
    # 2. 生成图论路由航线
    uav_paths = build_routes_from_graph(campus_hubs, relay_hubs)
    
    # 3. 渲染高德全要素底图
    amap_tiles = 'https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}'
    m = folium.Map(location=MAP_CENTER, zoom_start=14, tiles=amap_tiles, attr='&copy; 高德地图 AMAP')
    
    # 建立防御辐射圈
    folium.Circle(location=MAP_CENTER, radius=5000, color='#7B68EE', fill=True, fill_color='#7B68EE', fill_opacity=0.015, dash_array='6, 12').add_to(m)

    # 创建独立的图层组
    l_merchants = folium.FeatureGroup(name='🔴 供应端：外卖商户').add_to(m)
    l_relays = folium.FeatureGroup(name='🔵 枢纽端：河道接力柜').add_to(m)
    l_campus = folium.FeatureGroup(name='🟢 终端端：校园外卖柜').add_to(m)
    l_routes = folium.FeatureGroup(name='🛸 动态航路：流光水网廊道').add_to(m)

    # 绘制商户 (如果抓取了数据就会显示)
    for name, info in merchants.items():
        folium.Marker(location=info[:2], tooltip=name, icon=folium.Icon(color='red', icon='shopping-cart', prefix='fa')).add_to(l_merchants)

    # 绘制接力柜
    for name, info in relay_hubs.items():
        folium.Marker(location=info[:2], popup=f"{name}<br>归属:{info[2]}", tooltip=name, icon=folium.Icon(color='blue', icon='cloud', prefix='fa')).add_to(l_relays)

    # 绘制校园终端柜
    for name, coord in campus_hubs.items():
        folium.Marker(location=coord, tooltip=name, icon=folium.Icon(color='green', icon='home', prefix='fa')).add_to(l_campus)

    # 🚀 震撼画线：渲染 Dijkstra 算出的 100% 贴河动态光流路径
    for route in uav_paths:
        AntPath(locations=route["path"], delay=650, color='#00FFCC', pulse_color='#1E90FF', weight=6, opacity=0.9, tooltip=route["desc"]).add_to(l_routes)

    folium.LayerControl(position='topright').add_to(m)
    m.save("uav_delivery_dashboard.html")
    print("\n👑 画图程序已与数据库实现容错解耦！")
    print("📂 请打开同目录下的 'uav_delivery_dashboard.html'\n")

if __name__ == '__main__':
    main_render()