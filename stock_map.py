import pandas as pd
from io import BytesIO
from io import StringIO
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

def industry_classification():
    result = []
    url = 'https://blog.naver.com/PostView.naver?blogId=taelyon&logNo=223507138478'
    req = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, verify=True)
    soup = BeautifulSoup(req.text, features="lxml")
    box_type_l = soup.find("div", {"class": "se-table-container"})
    type_2 = box_type_l.find("table", {"class": "se-table-content"})
    tbody = type_2.find("tbody")
    trs = tbody.findAll("tr")
    stockInfos = []
    for tr in trs:
        try:
            tds = tr.findAll("td")
            industry = tds[0].text[1:-1]
            class_id = tds[1].text[1:-1]
            stockInfo = {"업종": industry, "분류": class_id}
            stockInfos.append(stockInfo)
        except Exception as e:
            pass
    list = stockInfos
    result += list

    df_industry = pd.DataFrame(result)
    df_industry = df_industry.drop(df_industry.index[0])
    return df_industry

# 코스피 시세 정보 수집 함수
def krx_sise_kospi(date_str):
    gen_req_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
    query_str_parms = {
        'locale': 'ko_KR',
        'mktId': 'STK',
        'trdDd': date_str,
        'money': '1',
        'csvxls_isNo': 'false',
        'name': 'fileDown',
        'url': 'dbms/MDC/STAT/standard/MDCSTAT03901'
    }
    headers = {
        'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020506',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'
    }

    r = requests.get(gen_req_url, query_str_parms, headers=headers)
    gen_req_url = 'http://data.krx.co.kr/comm/fileDn/download_excel/download.cmd'
    form_data = {
        'code': r.content
    }
    
    r = requests.post(gen_req_url, form_data, headers=headers)
    
    df_sise = pd.read_excel(BytesIO(r.content), engine='openpyxl')
    return df_sise

# 코스닥 시세 정보 수집 함수
def krx_sise_kosdaq(date_str):
    gen_req_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
    query_str_parms = {
        'locale': 'ko_KR',
        'mktId': 'KSQ',
        'segTpCd': 'ALL',
        'trdDd': date_str,
        'money': '1',
        'csvxls_isNo': 'false',
        'name': 'fileDown',
        'url': 'dbms/MDC/STAT/standard/MDCSTAT03901'
    }
    headers = {
        'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020506',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'
    }

    r = requests.get(gen_req_url, query_str_parms, headers=headers)
    gen_req_url = 'http://data.krx.co.kr/comm/fileDn/download_excel/download.cmd'
    form_data = {
        'code': r.content
    }
    
    r = requests.post(gen_req_url, form_data, headers=headers)
    
    df_sise = pd.read_excel(BytesIO(r.content), engine='openpyxl')
    return df_sise

# 최근 거래일의 코스피 시세 정보 수집
date = datetime.today()
while True:
    date_str = date.strftime('%Y%m%d')     
    df_sise_kospi = krx_sise_kospi(date_str)
    df_sise_kosdaq = krx_sise_kosdaq(date_str)

    if df_sise_kospi['종가'].apply(pd.to_numeric, errors='coerce').notnull().all() and df_sise_kosdaq['종가'].apply(pd.to_numeric, errors='coerce').notnull().all():
        break       
    date -= timedelta(days=1)
df_sise_kospi = df_sise_kospi[['종목코드', '종목명', '등락률', '시가총액']]
df_sise_kosdaq = df_sise_kosdaq[['종목코드', '종목명', '등락률', '시가총액']]
df_combined = pd.concat([df_sise_kospi, df_sise_kosdaq])


# # 종목 정보 수집
url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download'
response = requests.get(url)
html = response.content
soup = BeautifulSoup(html, 'html.parser')
table = soup.find('table')
df_info = pd.read_html(StringIO(str(table)))[0]
df_info = df_info[['종목코드', '업종']]
df_info['종목코드'] = df_info['종목코드'].apply(lambda x: f'{x:06d}')

df_merged = pd.merge(df_combined, df_info, on='종목코드')

df_industry = industry_classification()

df_final = pd.merge(df_merged, df_industry, on='업종', how='left')

# 시가총액이 가장 큰 상위 10개 종목 추출
df_top500 = df_final.sort_values(by='시가총액', ascending=False).head(500).reset_index(drop=True)

# Define custom color scale
color_scale = [
    (0.0, "rgb(246,53,56)"),      
    (0.16, "rgb(191,65,68)"),    
    (0.33, "rgb(139,67,78)"),    
    (0.5, "rgb(63,71,84)"),   
    (0.66, "rgb(52,118,80)"),     
    (0.83, "rgb(49,158,79)"),      
    (1.0, "rgb(48,191,86)")  
]

fig = px.treemap(df_top500,
                 path=['분류', '종목명'],
                 values='시가총액',
                 color='등락률',
                 color_continuous_scale=color_scale,
                 range_color=[-2.5, 2.5],
                 custom_data=['등락률'],
                 width=1450, height=690,
                 )
fig.update_traces(
    texttemplate='<b>%{label}</b><br>%{customdata[0]:.2f}%',
    textposition='middle center',
    marker_line=dict(color='gray'),
    textfont=dict(color='white'),
    hovertemplate='<b>%{label}</b><br>시가총액: %{value}<br>등락률: %{customdata[0]:.2f}%<extra></extra>'
)
fig.update_layout(coloraxis_showscale=False)
# 트리맵 보여주기
fig.show()
