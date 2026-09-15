#!/usr/bin/env python3
"""国内网络定时补充：只更新GitHub的tenders.json，不拉取或改写原始行情。"""
from __future__ import annotations
import base64
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 源文件与运行器放在同一专用目录，亦支持从仓库scripts目录运行。
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT if (ROOT/'fetch_tenders.py').exists() else ROOT.parent))
import fetch_tenders as ft

REPO='xianhuixu/reits-dashboard'
ENDPOINT=f'repos/{REPO}/contents/tenders.json'
LOG=logging.getLogger('tender-local')

def api(method: str, endpoint: str, payload: dict[str,Any] | None = None) -> dict[str,Any]:
    args=['gh','api','--method',method,endpoint]
    if payload is not None:
        args+=['--input','-']
    result=subprocess.run(args,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True,timeout=60,check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:250])
    return json.loads(result.stdout) if result.stdout.strip() else {}

def read_feed() -> tuple[dict[str,Any],str]:
    response=api('GET',ENDPOINT)
    return json.loads(base64.b64decode(response['content'])),response['sha']

def main() -> int:
    logging.basicConfig(level=logging.INFO,format='[tender-local] %(asctime)s %(message)s')
    old,_=read_feed()
    payload=ft.collect(old)
    payload['runner']='本机网络补充'
    payload['schedule']='云端每日09:20/18:20；本机补充09:50/18:50（北京时间；Mac需开机联网）'
    for attempt in range(3):
        current,sha=read_feed()
        # 并发写入时只合并专用信息流；不覆盖更新期间新增的公告。
        payload['items']=ft.merge_items(current.get('items',[]),payload['items'],datetime.fromisoformat(payload['checkedAt']).date())
        payload['latestBulletinDate']=max((x['date'] for x in payload['items']),default=None)
        for source in payload['sources']:
            previous=next((s for s in current.get('sources',[]) if s['id']==source['id']),{})
            successful=[t for t in [source.get('lastSuccessAt'),previous.get('lastSuccessAt')] if t]
            source['lastSuccessAt']=max(successful) if successful else None
        successful=[t for t in [payload.get('lastSuccessAt'),current.get('lastSuccessAt')] if t]
        payload['lastSuccessAt']=max(successful) if successful else None
        content=json.dumps(payload,ensure_ascii=False,indent=2)+'\n'
        try:
            response=api('PUT',ENDPOINT,{'message':'data: 本机补充招投标公告及来源状态','sha':sha,'branch':'main','content':base64.b64encode(content.encode()).decode()})
            LOG.info('已发布 %s status=%s items=%d',response['commit']['sha'],payload['status'],len(payload['items']))
            return 1 if payload['status']=='failed' else 0
        except RuntimeError as error:
            if '409' not in str(error) or attempt==2:
                raise
            LOG.warning('数据并发更新，重新合并后重试')
    return 1

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        LOG.exception('本机招投标更新失败')
        raise SystemExit(1)
