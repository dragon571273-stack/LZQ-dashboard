#!/usr/bin/env python3
"""独立招投标更新：ctbpsp 公开页面优先，官方 HTTPS 列表和公开资讯补充。"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode, urlparse
import requests
from zoneinfo import ZoneInfo

LOG = logging.getLogger('tenders')
TZ = ZoneInfo('Asia/Shanghai')
ROOT = Path(__file__).resolve().parent
LIST_URL = 'https://ctbpsp.com/#/bulletinList?keyWords=reits'
SOURCE_NAMES = {'ctbpsp':'中国招标投标公共服务平台（新站）','ceb':'中国招标投标公共服务平台（官方备用列表）','szwater':'深圳环水集团官网采购公告（补充）'}
REITS = re.compile(r'(?<![a-z])reits?(?![a-z])', re.I)
BID_WORDS = re.compile(r'招标|中标|采购|选聘|遴选|比选|磋商|成交|投标')


def request_text(url: str) -> str:
    """有限重试；公开页面不可用时明确失败，不伪造空结果。"""
    for attempt in range(2):
        try:
            response = requests.get(url, headers={'User-Agent':'Mozilla/5.0 (compatible; REITsResearch/1.0)'}, timeout=25)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except (requests.RequestException, ValueError) as error:
            LOG.warning('请求失败 %s attempt=%d: %s', urlparse(url).netloc, attempt+1, error)
            if attempt == 1:
                raise
            time.sleep(2)
    raise RuntimeError('请求未完成')


def clean(value: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', value))).strip()


def valid_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except (ValueError, TypeError):
        return False


def item(title: str, published: str, url: str, source: str) -> dict[str, Any]:
    key = hashlib.sha256((published+title).encode()).hexdigest()[:20]
    return {'code':'bid_'+key,'date':published,'title':title,'url':url,'source':source,
            'tag':'招投标','media':SOURCE_NAMES[source],
            'summary':'招投标公告线索；请以链接中的原始公告及后续更正为准。'}


def ceb_url(page: int, cutoff: date) -> str:
    return 'https://bulletin.cebpubservice.com/xxfbcmses/search/bulletin.html?'+urlencode({
        'searchDate':cutoff.isoformat(),'dates':30,'word':'REITs','page':page})


def parse_ceb(raw: str) -> tuple[list[dict[str, Any]], int]:
    """只用公告发布时间；开标截止时间不能作为信息流日期。"""
    total = re.search(r'id\s*=\s*[\"\']pageTotal[\"\'][^>]*value=[\"\']\s*(\d+)',raw)
    if not total:
        raise ValueError('官方备用列表结构缺失，不能确认空结果')
    rows: list[dict[str, Any]] = []
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw,re.S|re.I):
        title = re.search(r'<a\b[^>]*title=[\"\']([^\"\']+)',tr,re.I)
        uid = re.search(r"urlOpen\('([a-zA-Z0-9-]+)'\)",tr)
        published = re.search(r'name=[\"\']imgShow[\"\'][^>]*id=[\"\'](\d{4}-\d{2}-\d{2})',tr)
        if not (title and uid and published):
            continue
        text = clean(title.group(1))
        if REITS.search(text):
            url = 'https://ctbpsp.com/#/bulletinDetail?'+urlencode({'uuid':uid.group(1),'inpvalue':'','dataSource':0,'tenderAgency':''})
            rows.append(item(text,published.group(1),url,'ceb'))
    return rows, int(total.group(1))


def fetch_ceb(cutoff: date) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen_pages: set[str] = set()
    total = 0
    for page in range(1,21):
        current, total = parse_ceb(request_text(ceb_url(page,cutoff)))
        fingerprint = json.dumps([(x['title'],x['date']) for x in current],ensure_ascii=False)
        if fingerprint in seen_pages and current:
            return {'items':rows,'status':'partial','error':'分页返回重复内容，覆盖不完整'}
        seen_pages.add(fingerprint)
        rows.extend(current)
        if len(rows) >= total:
            return {'items':rows,'status':'ok','pages':page}
        # 列表并非严格按日期排序，不能在遇到一条旧公告后提前终止。
        time.sleep(1)
    return {'items':rows,'status':'partial','error':f'超过20页上限，列表共{total}条'}


CTB_READ = r"""() => {
 const boxes=[...document.querySelectorAll('.left_body')];
 if(boxes.some(b=>getComputedStyle(b).filter.includes('blur')))return {restricted:true,items:[]};
 return {restricted:false,items:boxes.map(b=>{
  const title=b.querySelector('.left_body_name');
  const dates=[...b.querySelectorAll('span')].map(x=>x.textContent).find(x=>/接收时间/.test(x));
  const match=dates&&dates.match(/20\d{2}-\d{2}-\d{2}/);
  const a=b.querySelector('a[href*="bulletinDetail"]');
  return {title:title?title.textContent.trim():'',date:match?match[0]:'',url:a?a.href:''};
 }).filter(x=>x.title&&x.date)};
}"""


def fetch_ctbpsp(cutoff: date) -> dict[str, Any]:
    """正常浏览器读取可见公开结果；不绕过登录、模糊遮罩或访问验证。"""
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
    rows: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as error:
            if "Executable doesn't exist" not in str(error):
                raise
            browser = playwright.chromium.launch(headless=True, channel='chrome')
        try:
            page = browser.new_page(locale='zh-CN')
            page.goto(LIST_URL,wait_until='domcontentloaded',timeout=45000)
            try:
                page.wait_for_selector('.left_body',timeout=25000)
            except Exception:
                body = page.locator('body').inner_text()
                if re.search(r'暂无(?:相关)?(?:公告|数据|结果)|未找到相关',body):
                    return {'items':[],'status':'ok','pages':1}
                raise RuntimeError('公开列表未加载：访问验证、登录限制或源站异常；不等同于无新增公告')
            for number in range(1,21):
                data = page.evaluate(CTB_READ)
                if data['restricted']:
                    raise RuntimeError('列表包含访问限制遮罩，未读取受限内容')
                current = data['items']
                if not current:
                    raise RuntimeError('公告日期或标题结构变化')
                for row in current:
                    title = clean(row['title'])
                    url = row['url'] or 'https://ctbpsp.com/#/bulletinList?keyWords='+quote(title)
                    rows.append(item(title,row['date'],url,'ctbpsp'))
                next_page = page.locator('.pagination .page-item a').filter(has_text=re.compile('^'+str(number+1)+'$'))
                if not next_page.count():
                    return {'items':rows,'status':'ok','pages':number}
                if number==20:
                    return {'items':rows,'status':'partial','error':'达到20页上限，覆盖不完整'}
                first = current[0]['title']
                next_page.first.click()
                page.wait_for_function("old => document.querySelector('.left_body_name')?.textContent.trim() !== old",arg=first,timeout=15000)
                page.wait_for_timeout(1200)
        finally:
            browser.close()
    return {'items':rows,'status':'partial','error':'列表未完成'}


def fetch_szwater(cutoff: date) -> dict[str, Any]:
    """官网首页公开的最新采购公告作补充，不宣称覆盖历史完整列表。"""
    raw = request_text('https://cg.sz-water.com.cn/')
    if '交易信息' not in raw or '.jhtml' not in raw:
        raise ValueError('深圳环水采购官网结构异常')
    rows: list[dict[str, Any]] = []
    for li in re.findall(r'<li\b[^>]*>(.*?)</li>',raw,re.S|re.I):
        title = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*title="([^"]+)"',li,re.I)
        published = re.search(r'(20\d{2}-\d{2}-\d{2})',li)
        if title and published and REITS.search(title.group(2)):
            url = title.group(1)
            if url.startswith('/'):
                url = 'https://cg.sz-water.com.cn'+url
            rows.append(item(clean(title.group(2)),published.group(1),url,'szwater'))
    return {'items':rows,'status':'ok','scope':'官网首页最新公告，仅作补充'}


def merge_items(old: list[dict[str, Any]], new: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """完整标题去重，保留同项目前缀的法律、审计及结果公告。"""
    unique: dict[tuple[str,str],dict[str,Any]] = {}
    rank = {'ctbpsp':0,'ceb':1,'szwater':2}
    for row in old+new:
        title = clean(str(row.get('title','')))
        published = row.get('date','')
        if not valid_date(published) or not (today-timedelta(days=90)<=date.fromisoformat(published)<=today):
            continue
        if not REITS.search(title) or urlparse(row.get('url','')).scheme not in ('http','https'):
            continue
        key = (published,re.sub(r'\s+','',title).casefold())
        previous = unique.get(key)
        if previous is None or rank.get(row.get('source'),3)<=rank.get(previous.get('source'),3):
            unique[key] = dict(row,title=title,tag='招投标')
    return sorted(unique.values(),key=lambda x:(x['date'],x['title']),reverse=True)


def build_payload(previous: dict[str,Any], results: list[dict[str,Any]], checked: str) -> dict[str,Any]:
    today = datetime.fromisoformat(checked).date()
    old_sources = {x['id']:x for x in previous.get('sources',[])}
    sources = []
    new: list[dict[str,Any]] = []
    for result in results:
        fresh = merge_items([],result.get('items',[]),today)
        new.extend(fresh)
        successful = result['status']=='ok'
        old = old_sources.get(result['id'],{})
        sources.append({k:v for k,v in dict(result,name=SOURCE_NAMES[result['id']],checkedAt=checked,
            count=len(fresh),latestBulletinDate=max((x['date'] for x in fresh),default=None),
            lastSuccessAt=checked if successful else old.get('lastSuccessAt')).items() if k!='items'})
    success = any(x['status']=='ok' for x in sources)
    primary = next((x for x in sources if x['id']=='ctbpsp'),{})
    status = 'ok' if primary.get('status')=='ok' else 'degraded' if success or new else 'failed'
    items = merge_items(previous.get('items',[]),new,today)
    return {'checkedAt':checked,'lastSuccessAt':checked if success else previous.get('lastSuccessAt'),
            'status':status,'schedule':'每日北京时间09:20、18:20（调度可能延迟）','retentionDays':90,
            'latestBulletinDate':max((x['date'] for x in items),default=None),'sources':sources,'items':items}


def collect(previous: dict[str,Any]) -> dict[str,Any]:
    now = datetime.now(TZ)
    cutoff = now.date()-timedelta(days=30)
    results = []
    adapters: list[tuple[str,Callable[[date],dict[str,Any]]]] = [('ctbpsp',fetch_ctbpsp),('ceb',fetch_ceb),('szwater',fetch_szwater)]
    for source, adapter in adapters:
        try:
            result = adapter(cutoff)
        except Exception as error:
            LOG.warning('%s 抓取失败: %s',source,error)
            result = {'status':'failed','items':[],'error':str(error)[:220]}
        result['id'] = source
        LOG.info('%s status=%s count=%d',source,result['status'],len(result['items']))
        results.append(result)
    return build_payload(previous,results,now.isoformat(timespec='seconds'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'tenders.json')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='[tenders] %(message)s')
    previous: dict[str,Any] = {}
    if args.output.exists():
        previous = json.loads(args.output.read_text(encoding='utf-8'))
    elif (ROOT/'news.json').exists():
        # 首次建立专用信息流时继承历史公告；不修改新闻原文件。
        news = json.loads((ROOT/'news.json').read_text(encoding='utf-8'))
        previous['items'] = [x for x in news.get('items',[]) if x.get('tag')=='招投标']
    payload = collect(previous)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    LOG.info('完成 status=%s 保留=%d 最新公告=%s',payload['status'],len(payload['items']),payload['latestBulletinDate'])
    return 1 if payload['status']=='failed' else 0

if __name__=='__main__':
    raise SystemExit(main())
