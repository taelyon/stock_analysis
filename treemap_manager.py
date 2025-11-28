import pandas as pd
import plotly.express as px
import DBUpdater_new
import os

class TreemapManager:
    def __init__(self):
        self.db = DBUpdater_new.MarketDB()

    def map_to_major_sector(self, sector):
        """세부 업종을 약 20개의 대분류로 매핑합니다."""
        if not isinstance(sector, str):
            return "기타"
            
        sector = sector.strip()
        
        # 1. 반도체
        if '반도체' in sector:
            return "반도체"
        # 2. IT하드웨어/가전
        elif any(k in sector for k in ['전기제품', '전자장비', '디스플레이', '핸드셋', '컴퓨터', '사무용전자', '통신장비', '전자부품', '전기장비', '전자제품', '가정용기기']):
            return "IT하드웨어/가전"
        # 3. 소프트웨어/서비스
        elif any(k in sector for k in ['소프트웨어', 'IT서비스', '인터넷', '미디어와서비스', '상업서비스']):
            return "소프트웨어/서비스"
        # 4. 제약/바이오
        elif any(k in sector for k in ['제약', '생물', '생명과학']):
            return "제약/바이오"
        # 5. 의료기기/서비스
        elif '건강' in sector or '의료' in sector:
            return "의료기기/서비스"
        # 6. 자동차/부품
        elif '자동차' in sector:
            return "자동차/부품"
        # 7. 화학/정유
        elif any(k in sector for k in ['화학', '석유', '가스', '정유']):
            return "화학/정유"
        # 8. 2차전지/에너지
        elif any(k in sector for k in ['에너지', '전력', '태양광']):
            return "2차전지/에너지"
        # 9. 철강/금속/광물
        elif any(k in sector for k in ['철강', '금속', '광물']):
            return "철강/금속/광물"
        # 10. 건설/건축
        elif any(k in sector for k in ['건설', '건축']):
            return "건설/건축"
        # 11. 조선/기계/방산
        elif any(k in sector for k in ['조선', '기계', '우주', '국방', '방위']):
            return "조선/기계/방산"
        # 12. 운송/물류
        elif any(k in sector for k in ['해운', '항공', '운송', '물류']):
            return "운송/물류"
        # 13. 금융/지주
        elif any(k in sector for k in ['은행', '증권', '보험', '금융', '카드', '투자', '부동산', '지주', '복합기업']):
            return "금융/지주"
        # 14. 식음료
        elif any(k in sector for k in ['식품', '음료', '담배', '식료']):
            return "식음료"
        # 15. 유통/상사
        elif any(k in sector for k in ['백화점', '상점', '무역', '판매', '소매', '상사']):
            return "유통/상사"
        # 16. 화장품/의류
        elif any(k in sector for k in ['화장품', '섬유', '의류', '신발', '가정용품']):
            return "화장품/의류"
        # 17. 미디어/엔터/게임
        elif any(k in sector for k in ['방송', '엔터', '게임', '광고', '출판', '영화']):
            return "미디어/엔터/게임"
        # 18. 호텔/레저
        elif any(k in sector for k in ['호텔', '레스토랑', '레저', '여행', '카지노']):
            return "호텔/레저"
        # 19. 통신
        elif '통신' in sector:
            return "통신"
        # 20. 유틸리티
        elif any(k in sector for k in ['유틸리티', '수도']):
            return "유틸리티"
        else:
            # 기타로 분류되는 경우 가장 유사한 '유통/상사'나 '소프트웨어/서비스'로 통합하거나
            # '기타'라는 이름 대신 '복합/기타'로 변경
            return "복합/기타"

    def generate_treemap(self):
        """
        DB에서 종목 정보를 가져와 트리맵 HTML을 생성합니다.
        """
        try:
            # DB에서 데이터 가져오기
            conn, cur = self.db._get_db_conn()
            # sector 컬럼 추가 조회
            sql = "SELECT company, market, sector, marcap, changes_ratio FROM comp_info WHERE country='kr' AND marcap IS NOT NULL"
            df = pd.read_sql(sql, conn)
            
            if df.empty:
                return "<h3>데이터가 없습니다. 종목 업데이트를 먼저 진행해주세요.</h3>"

            # 데이터 전처리
            # 시가총액이 너무 작은 종목은 제외 (상위 300개 정도만 표시하여 가독성 확보)
            df = df.sort_values(by='marcap', ascending=False).head(300)
            
            # 업종 정보가 없는 경우 '기타'로 처리
            df['sector'] = df['sector'].fillna('기타')
            
            # 대분류 매핑 적용
            df['major_sector'] = df['sector'].apply(self.map_to_major_sector)
            
            # 등락률에 따른 색상 스케일 설정을 위해 범위 제한 (-5% ~ +5%) - 민감도 대폭 증가
            df['changes_ratio'] = df['changes_ratio'].clip(-5, 5)
            
            # 트리맵 생성
            # path: 계층 구조 (대분류 -> 세부업종 -> 종목명)
            # values: 타일 크기 (시가총액)
            # color: 타일 색상 (등락률)
            fig = px.treemap(
                df, 
                path=[px.Constant("한국 증시"), 'major_sector', 'sector', 'company'], 
                values='marcap',
                color='changes_ratio',
                color_continuous_scale='RdBu_r', 
                color_continuous_midpoint=0,
                hover_data={'changes_ratio': ':.2f%', 'marcap': ':,.0f', 'sector': True},
                title='국내 증시 대분류별 트리맵 (시가총액 상위 300, ±5% 기준)'
            )

            # 레이아웃 및 디자인 개선
            fig.update_traces(
                textinfo="label+text",
                textposition="middle center",
                textfont=dict(family="Malgun Gothic", size=16), # 폰트 크기 증가
                marker=dict(
                    line=dict(width=2, color='white'), # 경계선 두께 증가로 업종 구분 강화
                    pad=dict(t=30) # 상단 여백 확보 (업종명 표시 공간)
                ),
                root_color="lightgrey"
            )

            fig.update_layout(
                margin=dict(t=50, l=10, r=10, b=10),
                coloraxis_colorbar=dict(
                    title="등락률 (%)",
                    tickvals=[-5, -2.5, 0, 2.5, 5],
                    ticktext=["-5%↓", "-2.5%", "0%", "+2.5%", "+5%↑"]
                ),
                font=dict(family="Malgun Gothic", size=14),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            # 텍스트 템플릿 설정
            fig.data[0].texttemplate = "<b>%{label}</b><br>%{customdata[0]:.2f}%"

            # HTML로 변환
            return fig.to_html(include_plotlyjs='cdn')

        except Exception as e:
            return f"<h3>트리맵 생성 중 오류 발생: {str(e)}</h3>"
