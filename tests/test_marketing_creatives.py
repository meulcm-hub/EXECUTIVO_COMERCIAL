import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import marketing_creatives as collector


class CreativeCollectorTests(unittest.TestCase):
    def row(self, **values):
        return {"ad_id": "123456", "campaign_id": "654321", "ad_name": "Anúncio teste",
                "campaign_name": "Campanha teste", "date_start": "2026-01-02",
                "spend": "12.34", "impressions": "100", "clicks": "5", **values}

    def test_month_chunks_cover_leap_and_year_boundaries_without_duplicates(self):
        self.assertEqual(list(collector.month_ranges(dt.date(2024, 2, 28), dt.date(2024, 3, 2))),
                         [(dt.date(2024, 2, 28), dt.date(2024, 2, 29)),
                          (dt.date(2024, 3, 1), dt.date(2024, 3, 2))])
        self.assertEqual(list(collector.month_ranges(dt.date(2026, 12, 31), dt.date(2027, 1, 1))),
                         [(dt.date(2026, 12, 31), dt.date(2026, 12, 31)),
                          (dt.date(2027, 1, 1), dt.date(2027, 1, 1))])

    def test_daily_ad_metrics_preserve_money_and_do_not_publish_additive_reach(self):
        rows = [self.row(reach="99", actions=[{"action_type": collector.FORM_ACTION, "value": "2"}]),
                self.row(date_start="2026-01-03", spend="4.56", impressions="40", clicks="1")]
        ads = collector.metric_rows(rows, dt.date(2026, 1, 1), dt.date(2026, 1, 31))
        self.assertEqual(set(ads), {"123456"})
        self.assertEqual(list(ads["123456"]["daily"]), ["2026-01-02", "2026-01-03"])
        daily = ads["123456"]["daily"]["2026-01-02"]
        self.assertEqual(daily["spend"], "12.34")
        self.assertEqual(daily["form_leads"], 2)
        self.assertNotIn("reach", daily)
        for invalid in ([rows[0], rows[0]], [self.row(date_start="2025-12-31")],
                        [self.row(impressions="1.5")], [self.row(spend="NaN")]):
            with self.assertRaises(RuntimeError):
                collector.metric_rows(invalid, dt.date(2026, 1, 1), dt.date(2026, 1, 31))

    def test_media_urls_reject_credentials_foreign_hosts_and_preserve_cdn_signature(self):
        signed = "https://scontent.test.fbcdn.net/video.mp4?oh=valid-signature&oe=ABCD&_nc_cat=2"
        self.assertEqual(collector.safe_url(signed), signed)
        for url in ("http://scontent.test.fbcdn.net/a.jpg", "https://fbcdn.net.evil.test/a.jpg",
                    "https://user:password@facebook.com/a", "https://facebook.com:8080/a",
                    "https://lookaside.fbsbx.com/a?access_token=secret", "javascript:alert(1)",
                    "https://facebook.com/a?Authorization=secret"):
            self.assertEqual(collector.safe_url(url), "")
        with patch.object(collector.meta, "TOKEN", "private-test-token"):
            self.assertEqual(collector.safe_url("https://facebook.com/a?x=private-test-token"), "")
            self.assertEqual(collector.clean_text("name private-test-token"), "")

    def test_regular_video_uses_direct_source_and_falls_back_without_permission(self):
        creative = {"video_id": "123456", "thumbnail_url": "https://scontent.test.fbcdn.net/thumb.jpg",
                    "effective_object_story_id": "111111_222222", "body": "Texto público"}
        result = collector.extract_media(creative, lambda _: {"source": "https://video.test.fbcdn.net/video.mp4"})
        self.assertEqual(result["media_type"], "video")
        self.assertEqual(result["video_url"], "https://video.test.fbcdn.net/video.mp4")
        self.assertEqual(result["permalink_url"], "https://www.facebook.com/111111/posts/222222")
        fallback = collector.extract_media(creative, lambda _: {})
        self.assertEqual(fallback["media_type"], "video")
        self.assertEqual(fallback["video_url"], "")
        self.assertTrue(fallback["image_url"].endswith("thumb.jpg"))
        self.assertEqual(fallback["permalink_url"], result["permalink_url"])

    def test_carousel_and_dynamic_assets_deduplicate_videos(self):
        creative = {"object_story_spec": {"link_data": {"child_attachments": [
                        {"picture": "https://scontent.test.fbcdn.net/image.jpg"}, {"video_id": "123456"}]}},
                    "asset_feed_spec": {"videos": [{"video_id": "123456"}],
                                        "images": [{"url": "https://scontent.test.fbcdn.net/other.jpg"}]}}
        result = collector.extract_media(creative, lambda _: {})
        self.assertEqual(result["media_type"], "carousel")
        self.assertEqual(len(result["media"]), 3)
        self.assertEqual([m["type"] for m in result["media"]], ["image", "video", "image"])
        self.assertTrue(result["media"][1]["permalink_url"].startswith("https://www.facebook.com/watch/"))

    def test_graph_object_never_accepts_different_identifier(self):
        with patch.object(collector.meta, "TOKEN", "private-test-token"), \
             patch.object(collector.GRAPH_OPENER, "open", return_value=io.BytesIO(b'{"id":"999999","source":"secret"}')):
            with self.assertRaisesRegex(RuntimeError, "identificador"):
                collector.graph_object("123456", "id,source")
        with self.assertRaises(RuntimeError):
            collector.graph_object("https://other.test/123456", "id")
        with self.assertRaisesRegex(RuntimeError, "Redirecionamento"):
            collector.NoGraphRedirect().redirect_request(None, None, 302, "", {}, "https://other.test/")

    def test_catalog_status_accounts_and_historical_ads_keep_correct_daily_binding(self):
        account = {"id": "act_347253318197280", "currency": "BRL", "name": "LCM Jacarandá"}
        catalog = [{"id": "123456", "name": "Mídia ativa", "campaign_id": "654321", "effective_status": "ACTIVE",
                    "campaign": {"id": "654321", "name": "Campanha atual", "effective_status": "PAUSED"},
                    "creative": {"image_url": "https://scontent.test.fbcdn.net/image.jpg"}}]
        catalog.extend([{**catalog[0], "id": "888888", "effective_status": "PAUSED"},
                        {**catalog[0], "id": "999999", "campaign": {"id": "654321", "effective_status": "ACTIVE"}}])
        rows = [self.row(), self.row(ad_id="555555", date_start="2026-01-03", ad_name="Removido")]
        with patch.object(collector.meta, "request", side_effect=[catalog, rows]) as request, \
             patch.object(collector, "graph_object", side_effect=RuntimeError("Mídia indisponível")):
            result = collector.collect_account(account, dt.date(2026, 1, 1), dt.date(2026, 1, 3), {})
        self.assertNotIn("effective_status", request.call_args_list[0].args[1])
        self.assertEqual(len(result), 3)
        by_id = {ad["ad_id"]: ad for ad in result}
        self.assertNotIn("888888", by_id)
        self.assertEqual(by_id["999999"]["status"], "ACTIVE")
        self.assertEqual(by_id["999999"]["daily"], [])
        self.assertEqual(by_id["123456"]["status"], "CAMPAIGN_PAUSED")
        self.assertEqual(by_id["555555"]["status"], "UNKNOWN")
        self.assertEqual(by_id["555555"]["name"], "Removido")
        self.assertEqual(by_id["555555"]["media_type"], "unknown")
        self.assertEqual(by_id["123456"]["project"], "residencial flores do cerrado jacaranda")
        self.assertEqual(sum(len(ad["daily"]) for ad in result), 2)

    def test_historical_ad_missing_from_default_catalog_gets_direct_media_metadata(self):
        account = {"id": "act_347253318197280", "currency": "BRL", "name": "LCM Jacarandá"}
        historical = {"id": "123456", "name": "Histórico pausado", "campaign_id": "654321",
                      "effective_status": "PAUSED",
                      "creative": {"image_url": "https://scontent.test.fbcdn.net/history.jpg"}}
        with patch.object(collector.meta, "request", side_effect=[[], [self.row()]]), \
             patch.object(collector, "graph_object", return_value=historical) as direct:
            result = collector.collect_account(account, dt.date(2026, 1, 1), dt.date(2026, 1, 3), {})
        direct.assert_called_once_with("123456", collector.AD_FIELDS)
        self.assertEqual(result[0]["status"], "PAUSED")
        self.assertEqual(result[0]["media_type"], "image")
        self.assertEqual(result[0]["image_url"], "https://scontent.test.fbcdn.net/history.jpg")
        self.assertEqual(result[0]["daily"][0]["spend"], "12.34")

    def test_primary_collection_failure_never_replaces_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "creatives.json"
            output.write_text('{"previous":true}', encoding="utf-8")
            with patch.object(collector, "collect", side_effect=RuntimeError("Safe failure")), \
                 patch.object(collector, "publish") as publish:
                with self.assertRaises(RuntimeError):
                    collector.main()
                publish.assert_not_called()
            self.assertEqual(json.loads(output.read_text()), {"previous": True})
            collector.publish({"schema_version": 1, "ads": []}, output)
            self.assertEqual(json.loads(output.read_text())["schema_version"], 1)
            self.assertFalse(output.with_name(output.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
