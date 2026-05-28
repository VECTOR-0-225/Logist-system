# -*- coding: utf-8 -*-
"""
📌 增量数据修正中心
功能：只想修改部分接力柜坐标时，直接运行此脚本精准更新数据库，不影响其他完美数据。
"""
import sqlite3

def update_relay_hub(hub_name, new_lat, new_lng, new_river=None):
    """
    精准更新某一个接力柜的坐标或归属水系
    """
    conn = sqlite3.connect('uav_logistic_system.db')
    cursor = conn.cursor()
    
    if new_river:
        # 同时修改坐标和绑定的河流名字
        cursor.execute("""
            UPDATE relay_hubs 
            SET lat = ?, lng = ?, river = ? 
            WHERE name = ?
        """, (new_lat, new_lng, new_river, hub_name))
    else:
        # 只修改坐标
        cursor.execute("""
            UPDATE relay_hubs 
            SET lat = ?, lng = ? 
            WHERE name = ?
        """, (new_lat, new_lng, hub_name))
        
    conn.commit()
    conn.close()
    print(f"✨ 成功：已将【{hub_name}】的坐标精准修正为: {new_lat}, {new_lng}")

if __name__ == '__main__':
    print("🚀 开始执行局部点位微调...")
    
    # 📝 在这里写你想修改的柜子（改哪个写哪个，不改的不写）
    # 示例：把2号接力柜往旁边挪一点，并强行换一条更连通的河道
    update_relay_hub(
        hub_name="智能接力柜 #16", 
        new_lat=30.254459,
        new_lng=120.171805,
        new_river="中河"
    )

    update_relay_hub(
        hub_name="智能接力柜 #14", 
        new_lat=30.258222,
        new_lng=120.179489,
        new_river="东河"
    )
    
    print("📢 提示：局部点位已更新！现在直接去运行你的‘画图大屏程序’，航线会自动重新计算并对齐！")