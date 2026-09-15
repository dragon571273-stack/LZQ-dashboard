"""招投标更新回归：结果、分页、去重、失败状态均须可验证。"""
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path
import fetch_tenders as ft

class TenderTests(unittest.TestCase):
    def test_official_parser_uses_publication_not_deadline(self) -> None:
        raw = Path('tests/fixtures/tenders/ceb-excerpt.html').read_text()
        rows, total = ft.parse_ceb(raw)
        self.assertEqual(total, 57)
        self.assertEqual(rows[1]['date'], '2026-09-04')
        self.assertIn('uuid=761b869c164040dda3a27d490133db95', rows[1]['url'])

    def test_official_url_uses_https_and_current_cutoff(self) -> None:
        url = ft.ceb_url(2, date(2026, 8, 16))
        self.assertTrue(url.startswith('https://'))
        self.assertIn('searchDate=2026-08-16', url)
        self.assertIn('page=2', url)

    def test_full_titles_preserve_distinct_service_announcements(self) -> None:
        prefix = '某基础设施公募REITs发行及相关服务采购项目'
        old = [self.item(prefix+'法律服务'), self.item(prefix+'审计服务')]
        merged = ft.merge_items(old, [dict(old[0], source='ctbpsp')], date(2026,9,15))
        self.assertEqual(len(merged),2)
        self.assertEqual(next(x for x in merged if '法律' in x['title'])['source'],'ctbpsp')

    def test_failed_sources_do_not_advance_success_time(self) -> None:
        prior = {'lastSuccessAt':'2026-09-01T00:00:00+08:00','items':[self.item('公募REITs招标公告')]}
        sources = [{'id':'ctbpsp','status':'failed','items':[],'error':'timeout'}]
        payload = ft.build_payload(prior,sources,'2026-09-15T18:20:00+08:00')
        self.assertEqual(payload['status'],'failed')
        self.assertEqual(payload['lastSuccessAt'],prior['lastSuccessAt'])
        self.assertEqual(len(payload['items']),1)

    def test_backup_success_is_degraded_not_primary_success(self) -> None:
        sources = [{'id':'ctbpsp','status':'failed','items':[]}, {'id':'ceb','status':'ok','items':[self.item('公募REITs招标公告')]}]
        p=ft.build_payload({},sources,'2026-09-15T18:20:00+08:00')
        self.assertEqual(p['status'],'degraded')
        self.assertEqual(p['sources'][0]['lastSuccessAt'],None)
        self.assertEqual(p['sources'][1]['count'],1)

    def test_no_unverified_future_dates(self) -> None:
        rows=[self.item('REITs招标公告'),dict(self.item('REITs中标公告'),date='2027-01-01')]
        self.assertEqual(len(ft.merge_items([],rows,date(2026,9,15))),1)

    def test_pagination_stops_at_actual_total_not_stale_html_page_size(self) -> None:
        pages = [([self.item(f'REITs招标{n}') for n in range(start,end)],57) for start,end in [(0,20),(20,40),(40,57)]]
        with patch.object(ft,'request_text',return_value='page'), patch.object(ft,'parse_ceb',side_effect=pages), patch.object(ft.time,'sleep'):
            result=ft.fetch_ceb(date(2026,8,16))
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['pages'],3)
        self.assertEqual(len(result['items']),57)

    def test_repeated_page_is_partial_not_success(self) -> None:
        page=([self.item('REITs招标公告')],2)
        with patch.object(ft,'request_text',return_value='page'), patch.object(ft,'parse_ceb',return_value=page), patch.object(ft.time,'sleep'):
            result=ft.fetch_ceb(date(2026,8,16))
        self.assertEqual(result['status'],'partial')
        self.assertEqual(len(result['items']),1)

    def test_daily_schedule_is_independent_of_market_update(self) -> None:
        workflow=Path('.github/workflows/tenders-update.yml').read_text()
        self.assertIn("20 1,10 * * *",workflow)
        self.assertNotIn('fetch_data_em.py',workflow)
        self.assertIn('pages/builds',workflow)

    @staticmethod
    def item(title: str) -> dict:
        return {'title':title,'date':'2026-09-04','url':'https://example.org/notice','source':'ceb','tag':'招投标'}

if __name__ == '__main__':
    unittest.main()
