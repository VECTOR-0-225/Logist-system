import json

# ==========================================
# 1. 读取你下载好的 GeoJSON 文件
# ==========================================
# 请把 'export.geojson' 替换成你真实的地理文件名
geojson_path = '/Users/vector/Desktop/code_python/无人机河道最优效率计算/export.geojson' 

try:
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)

    print("🎉 成功加载地理文件！开始解析河道骨架...")
    print("--------------------------------------------------")
    
    river_counter = 1
    # 用一个字典来存放解析出来的所有河道线
    ALL_EXTRACTED_RIVERS = {}

    # ==========================================
    # 2. 地毯式搜索文件中的“线（LineString）”几何结构
    # ==========================================
    features = geojson_data.get('features', [])
    
    for feature in features:
        geometry = feature.get('geometry', {})
        properties = feature.get('properties', {})
        
        # 获取这条河流在 OSM 上的名字（如果有的话，没有就用数字代替）
        river_name = properties.get('name', f"Unnamed_River_{river_counter}")
        
        # 我们只提取折线（LineString）类型的地理数据
        if geometry and geometry.get('type') == 'LineString':
            coordinates = geometry.get('coordinates', [])
            
            # GeoJSON 默认格式就是 [经度, 纬度]，这跟我们之前的算法完美契合！
            # 我们把它转换成元组列表：[(lon1, lat1), (lon2, lat2), ...]
            formatted_coordinates = [tuple(coord) for coord in coordinates]
            
            # 如果这条河的点太少（比如只有1个点，或者空的），就过滤掉
            if len(formatted_coordinates) > 1:
                # 为了防止重名，加上计数器
                unique_key = f"{river_name}_{river_counter}"
                ALL_EXTRACTED_RIVERS[unique_key] = formatted_coordinates
                river_counter += 1

    # ==========================================
    # 3. 打印解析成果
    # ==========================================
    print(f"✅ 解析成功！总共从地图中提取出 {len(ALL_EXTRACTED_RIVERS)} 段有效河道走廊。")
    print("# 💡 下面是提取出的前几条河道坐标示例（可直接用于画图和算法）：\n")
    
    # 我们只打印前3条来看看效果，防止屏幕被几万个坐标刷屏
    for idx, (name, coords) in enumerate(ALL_EXTRACTED_RIVERS.items()):
        if idx < 3:
            print(f"RIVER_{idx+1} = {coords[:5]} ... # 共 {len(coords)} 个坐标点")
            print("-" * 30)
            
except FileNotFoundError:
    print(f"❌ 找不到文件：'{geojson_path}'，请确保它和 Python 脚本在同一个文件夹下，或者填写绝对路径。")
except Exception as e:
    print(f"❌ 解析发生错误: {e}")