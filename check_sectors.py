import sqlite3
import pandas as pd
from treemap_manager import TreemapManager

def check_unmapped_sectors():
    tm = TreemapManager()
    conn = sqlite3.connect('investar.db')
    
    # 상위 300개 종목의 업종 조회
    sql = "SELECT sector, marcap FROM comp_info WHERE country='kr' AND marcap IS NOT NULL ORDER BY marcap DESC LIMIT 300"
    df = pd.read_sql(sql, conn)
    
    # 매핑 확인
    df['major'] = df['sector'].apply(tm.map_to_major_sector)
    
    # '기타'로 분류된 업종 출력
    unmapped = df[df['major'] == '기타']['sector'].unique()
    print("Unmapped sectors:", unmapped)

if __name__ == "__main__":
    check_unmapped_sectors()
