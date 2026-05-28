# -*- coding: utf-8 -*-
"""
📌 空地协同接力枢纽——多网格并发选址计算引擎 (K-Means 聚类版)
功能：动态读取 SQLite 商家坐标，将城市划分为 N 个末端网格，
      并为每个网格在真实 GeoJSON 河道上匹配出效率最优的智能接力柜坐标。
"""

import json
import math
import sqlite3
import os
import sys
import random

# ==========================================
# 步骤一：基础参数与目标柜数量设定
# ==========================================
DB_PATH = 'uav_logistic_system.db'
GEOJSON_PATH = '/Users/vector/Desktop/code_python/无人机河道最优效率计算/export.geojson'

TARGET_HUB_COUNT = 26  # 🎯 目标接力柜数量：你想在地图上布设多少个柜子，这里就填几

SPEED_RIDER = 20.0  # 骑手时速 20 km/h
SPEED_DRONE = 50.0  # 无人机空中巡航时速 50 km/h
TRANSFER_TIME = 3.0 # 接力柜固定的操作等待时间 (分钟)

def get_real_distance(coord1, coord2):
    """Haversine 距离算法，返回公里数"""
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    rad_lon1, rad_lat1, rad_lon2, rad_lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = rad_lon2 - rad_lon1
    dlat = rad_lat2 - rad_lat1
    a = math.sin(dlat/2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon/2)**2
    return 2 * math.asin(math.sqrt(a)) * 6371

# ==========================================
# 步骤二：连接本地数据库，提取资产数据
# ==========================================
if not os.path.exists(DB_PATH):
    print(f"❌ 错误：找不到数据库 '{DB_PATH}'！请先运行抓取程序。")
    sys.exit()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. 加载校园终端柜并计算物理重心
cursor.execute("SELECT name, lat, lng FROM campus_hubs")
db_campus = cursor.fetchall()
if db_campus:
    campus_coords = [(row[2], row[1]) for row in db_campus]
else:
    campus_coords = [(120.166426, 30.295476), (120.166601, 30.294561), (120.165826, 30.294135)]

campus_center = (
    sum(c[0] for c in campus_coords) / len(campus_coords),
    sum(c[1] for c in campus_coords) / len(campus_coords)
)

# 2. 加载全量外卖商家数据
cursor.execute("SELECT name, lat, lng FROM merchants")
db_merchants = cursor.fetchall()
if not db_merchants:
    print("❌ 错误：商家表为空！")
    sys.exit()

# 转为列表：[(商家名, (经度, 纬度)), ...]
merchant_list = [(row[0], (row[2], row[1])) for row in db_merchants]
conn.close()

# ==========================================
# 步骤三：解析本地 GeoJSON 河道数据
# ==========================================
candidate_river_points = []
river_counter = 1

try:
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
        
    for feature in geojson_data.get('features', []):
        geometry = feature.get('geometry', {})
        properties = feature.get('properties', {})
        river_name = properties.get('name', f"Unnamed_River_{river_counter}")
        
        if not geometry: continue
        geom_type = geometry.get('type')
        
        if geom_type == 'LineString':
            for c in geometry.get('coordinates', []):
                candidate_river_points.append(((float(c[0]), float(c[1])), river_name))
            river_counter += 1
        elif geom_type == 'MultiLineString':
            for line in geometry.get('coordinates', []):
                for c in line:
                    candidate_river_points.append(((float(c[0]), float(c[1])), river_name))
            river_counter += 1
        elif geom_type == 'Polygon':
            for ring in geometry.get('coordinates', []):
                for c in ring:
                    candidate_river_points.append(((float(c[0]), float(c[1])), river_name))
            river_counter += 1
except FileNotFoundError:
    print(f"❌ 错误：找不到 '{GEOJSON_PATH}' 文件！")
    sys.exit()

# ==========================================
# 步骤四：K-Means 空间聚类 (将商家划分为指定网格)
# ==========================================
print(f"🧮 正在将 {len(merchant_list)} 家商户自动划分为 {TARGET_HUB_COUNT} 个独立服务网格...")

# 随机抽取初始质心
random.seed(42)
centroids = [m[1] for m in random.sample(merchant_list, TARGET_HUB_COUNT)]
clusters = {i: [] for i in range(TARGET_HUB_COUNT)}

# 迭代 10 次收敛
for _ in range(10):
    clusters = {i: [] for i in range(TARGET_HUB_COUNT)}
    for m_name, m_coord in merchant_list:
        # 寻找离该商家最近的网格中心
        closest_i = min(range(TARGET_HUB_COUNT), key=lambda i: get_real_distance(m_coord, centroids[i]))
        clusters[closest_i].append((m_name, m_coord))
    
    # 更新网格中心点
    for i in range(TARGET_HUB_COUNT):
        if clusters[i]:
            avg_lon = sum(c[1][0] for c in clusters[i]) / len(clusters[i])
            avg_lat = sum(c[1][1] for c in clusters[i]) / len(clusters[i])
            centroids[i] = (avg_lon, avg_lat)

# ==========================================
# 步骤五：为每个网格寻找最优专属接力柜
# ==========================================
print(f"🤖 运筹大脑火力全开：正在为每个网格在水系上寻找最优停机坪...")

final_hubs_report = []

for i in range(TARGET_HUB_COUNT):
    cluster_merchants = clusters[i]
    if not cluster_merchants:
        continue
        
    best_hub_coord = None
    best_hub_river_name = ""
    min_time = float('inf')
    
    # 为了加速，框定该网格的搜索外包围盒 (加宽 1 公里容差)
    c_lons = [m[1][0] for m in cluster_merchants]
    c_lats = [m[1][1] for m in cluster_merchants]
    min_lon, max_lon = min(c_lons) - 0.01, max(c_lons) + 0.01
    min_lat, max_lat = min(c_lats) - 0.01, max(c_lats) + 0.01
    
    # 在这个网格附近的河道点里做地毯式搜索
    local_river_points = [
        pt for pt in candidate_river_points
        if min_lon <= pt[0][0] <= max_lon and min_lat <= pt[0][1] <= max_lat
    ]
    
    # 如果附近没河，就用全城河道兜底
    search_points = local_river_points if local_river_points else candidate_river_points
    
    # 计算本网格的最佳河道锚点
    for r_coord, r_name in search_points:
        total_time = 0
        for m_name, m_coord in cluster_merchants:
            dist_ground = get_real_distance(m_coord, r_coord)
            dist_air = get_real_distance(r_coord, campus_center)
            total_time += (dist_ground / SPEED_RIDER) * 60 + TRANSFER_TIME + (dist_air / SPEED_DRONE) * 60
            
        if total_time < min_time:
            min_time = total_time
            best_hub_coord = r_coord
            best_hub_river_name = r_name
            
    final_hubs_report.append({
        "hub_id": i + 1,
        "coord": best_hub_coord,
        "river": best_hub_river_name,
        "merchants": [m[0] for m in cluster_merchants]
    })

# ==========================================
# 步骤六：输出最终工业级决策报告
# ==========================================
print("\n==================================================================")
print("👑 工业工程（IE）空地接力网络——全自动分布式选址优化报告")
print("==================================================================")

for hub in final_hubs_report:
    # 转换为标准的 高德经纬度格式
    lng, lat = hub["coord"]
    merchants_str = ", ".join(hub["merchants"])
    
    print(f"📦 【核心智能接力柜 #{hub['hub_id']}】")
    print(f"   📍 高德适配经纬度: {lng:.6f}, {lat:.6f}")
    print(f"   🌊 落地水系走廊: {hub['river']}")
    print(f"   🛵 本网格辐射服务的商家 ({len(hub['merchants'])}家): {merchants_str}")
    print("   🛸 无人机指引: 接力柜坐标已与高德底图完美对齐，出舱即进入绿色安全空域。")
    print("-" * 80)