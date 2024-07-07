from bs4 import BeautifulSoup
from io import StringIO
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
import plotly.express as px

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
df_sise_kospi = df_sise_kospi[['종목코드', '종목명', '업종명', '등락률', '시가총액']]
df_sise_kosdaq = df_sise_kosdaq[['종목코드', '종목명', '업종명', '등락률', '시가총액']]

# 데이터프레임 병합
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
# print(df_info)

df_merged = pd.merge(df_combined, df_info, on='종목코드')

# 시가총액이 가장 큰 상위 10개 종목 추출
df_top500 = df_merged.sort_values(by='시가총액', ascending=False).head(500).reset_index(drop=True)
# print(df_top500)

fig = px.treemap(df_top500,
                 path=['업종명', '업종', '종목명'],
                 values='시가총액',
                 color='등락률',
                 color_continuous_scale='RdBu',
                 title='한국 주식 500 맵')

# 트리맵 보여주기
fig.show()