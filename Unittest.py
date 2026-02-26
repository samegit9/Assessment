#unittest

import unittest
import pandas as pd
from Controller import DataExtractor
# ── helper to build a minimal dataframe row ───────────────────────────────

def make_dataframe(rows):
    """Build a dataframe from a list of row dicts with sensible defaults."""
    defaults = {
        'ip':           '1.1.1.1',
        'date_time':    '2009-09-27 06:34:40',
        'referrer':     '',
        'page_url':     'http://www.esshopzilla.com',
        'product_list': '',
        'event_list':   '',
    }
    data = []
    for row in rows:
        r = defaults.copy()
        r.update(row)
        data.append(r)
    return pd.DataFrame(data)


# ── DataExtractor.extract_domain_and_keyword ──────────────────────────────

class TestExtractDomainAndKeyword(unittest.TestCase):

    def setUp(self):
        self.extractor = DataExtractor()

    def test_google_q_param(self):
        domain, keyword = self.extractor.extract_domain_and_keyword(
            "http://www.google.com/search?hl=en&q=Ipod&aq=f"
        )
        self.assertEqual(domain, 'google.com')
        self.assertEqual(keyword, 'ipod')          # lowercased

    def test_yahoo_p_param(self):
        domain, keyword = self.extractor.extract_domain_and_keyword(
            "http://search.yahoo.com/search?p=cd+player&fr=yfp"
        )
        self.assertEqual(domain, 'yahoo.com')
        self.assertEqual(keyword, 'cd player')     # + replaced with space

    def test_bing_q_param(self):
        domain, keyword = self.extractor.extract_domain_and_keyword(
            "http://www.bing.com/search?q=Zune&form=QBLH"
        )
        self.assertEqual(domain, 'bing.com')
        self.assertEqual(keyword, 'zune')

    def test_unknown_domain_returns_none(self):
        domain, keyword = self.extractor.extract_domain_and_keyword(
            "http://www.esshopzilla.com/cart/"
        )
        self.assertIsNone(domain)
        self.assertIsNone(keyword)

    def test_empty_string_returns_none(self):
        domain, keyword = self.extractor.extract_domain_and_keyword("")
        self.assertIsNone(domain)
        self.assertIsNone(keyword)

    def test_keyword_with_plus_signs(self):
        domain, keyword = self.extractor.extract_domain_and_keyword(
            "http://www.google.com/search?q=noise+cancelling+headphones"
        )
        self.assertEqual(keyword, 'noise cancelling headphones')

    def test_no_keyword_param_returns_none(self):
        # URL is a known engine but has no q= param
        domain, keyword = self.extractor.extract_domain_and_keyword(
            "http://www.google.com/"
        )
        self.assertIsNone(keyword)


# ── DataExtractor.extract_revenue ─────────────────────────────────────────

class TestExtractRevenue(unittest.TestCase):

    def setUp(self):
        self.extractor = DataExtractor()

    def test_purchase_event_returns_revenue(self):
        row = {'product_list': 'Electronics;Ipod;1;290;', 'event_list': '1'}
        self.assertEqual(self.extractor.extract_revenue(row), 290.0)

    def test_non_purchase_event_returns_zero(self):
        row = {'product_list': 'Electronics;Ipod;1;290;', 'event_list': '2'}
        self.assertEqual(self.extractor.extract_revenue(row), 0.0)

    def test_empty_product_list_returns_zero(self):
        row = {'product_list': '', 'event_list': '1'}
        self.assertEqual(self.extractor.extract_revenue(row), 0.0)

    def test_missing_revenue_field_returns_zero(self):
        row = {'product_list': 'Electronics;Ipod;1;;', 'event_list': '1'}
        self.assertEqual(self.extractor.extract_revenue(row), 0.0)

    def test_event_list_with_multiple_events(self):
        # purchase event among others
        row = {'product_list': 'Electronics;Zune;1;250;', 'event_list': '1,2,3'}
        self.assertEqual(self.extractor.extract_revenue(row), 250.0)

    def test_float_event_list(self):
        # pandas sometimes reads integers as floats (e.g. 1.0)
        row = {'product_list': 'Electronics;Ipod;1;190;', 'event_list': 1.0}
        self.assertEqual(self.extractor.extract_revenue(row), 190.0)

    def test_no_event_list_key_returns_zero(self):
        row = {'product_list': 'Electronics;Ipod;1;290;'}
        self.assertEqual(self.extractor.extract_revenue(row), 0.0)


# ── DataExtractor.format_date ─────────────────────────────────────────────

class TestFormatDate(unittest.TestCase):

    def setUp(self):
        self.extractor = DataExtractor()

    def test_standard_format(self):
        self.assertEqual(
            self.extractor.format_date('2009-09-27 06:34:40'),
            '2009-09-27'
        )

    def test_invalid_format_returned_as_is(self):
        # Should not crash, just return what it got
        result = self.extractor.format_date('27/09/2009')
        self.assertEqual(result, '27/09/2009')


# ── extract_revenue_data (integration) ────────────────────────────────────

class TestExtractRevenueData(unittest.TestCase):

    def test_basic_attribution(self):
        """A purchase by a visitor who came from Google should be attributed."""
        df = make_dataframe([
            # Hit 1: visitor arrives from Google
            {'ip': '1.1.1.1', 'referrer': 'http://www.google.com/search?q=Ipod'},
            # Hit 2: purchase
            {'ip': '1.1.1.1', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Ipod;1;290;', 'event_list': '1'},
        ])
        result, dates = extract_revenue_data(df)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['Search Engine Domain'], 'google.com')
        self.assertEqual(result.iloc[0]['Search Keyword'], 'ipod')
        self.assertEqual(result.iloc[0]['Revenue'], 290.0)

    def test_non_purchase_hit_ignored(self):
        """Hits without event 1 should not appear in results."""
        df = make_dataframe([
            {'ip': '1.1.1.1', 'referrer': 'http://www.google.com/search?q=Ipod'},
            {'ip': '1.1.1.1', 'referrer': 'http://www.esshopzilla.com/',
             'product_list': 'Electronics;Ipod;1;290;', 'event_list': '2'},
        ])
        result, _ = extract_revenue_data(df)
        self.assertEqual(len(result), 0)

    def test_no_search_engine_session_ignored(self):
        """A purchase by a visitor who never came from a search engine is excluded."""
        df = make_dataframe([
            {'ip': '9.9.9.9', 'referrer': 'http://www.esshopzilla.com/',
             'product_list': 'Electronics;Ipod;1;290;', 'event_list': '1'},
        ])
        result, _ = extract_revenue_data(df)
        self.assertEqual(len(result), 0)

    def test_revenue_grouped_and_summed(self):
        """Two purchases for the same engine+keyword should be summed into one row."""
        df = make_dataframe([
            # Visitor A
            {'ip': '1.1.1.1', 'referrer': 'http://www.google.com/search?q=Ipod'},
            {'ip': '1.1.1.1', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Ipod;1;290;', 'event_list': '1'},
            # Visitor B — same keyword
            {'ip': '2.2.2.2', 'referrer': 'http://www.google.com/search?q=Ipod'},
            {'ip': '2.2.2.2', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Ipod;1;190;', 'event_list': '1'},
        ])
        result, _ = extract_revenue_data(df)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['Revenue'], 480.0)

    def test_sorted_by_revenue_descending(self):
        """Results must be sorted highest revenue first."""
        df = make_dataframe([
            # Visitor A: Bing, Zune, $250
            {'ip': '1.1.1.1', 'referrer': 'http://www.bing.com/search?q=Zune'},
            {'ip': '1.1.1.1', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Zune;1;250;', 'event_list': '1'},
            # Visitor B: Google, Ipod, $480
            {'ip': '2.2.2.2', 'referrer': 'http://www.google.com/search?q=Ipod'},
            {'ip': '2.2.2.2', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Ipod;1;480;', 'event_list': '1'},
        ])
        result, _ = extract_revenue_data(df)
        revenues = result['Revenue'].tolist()
        self.assertEqual(revenues, sorted(revenues, reverse=True))
        self.assertEqual(revenues[0], 480.0)

    def test_multiple_engines_separate_rows(self):
        """Google and Bing keywords should produce separate rows."""
        df = make_dataframe([
            {'ip': '1.1.1.1', 'referrer': 'http://www.google.com/search?q=Ipod'},
            {'ip': '1.1.1.1', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Ipod;1;290;', 'event_list': '1'},
            {'ip': '2.2.2.2', 'referrer': 'http://www.bing.com/search?q=Zune'},
            {'ip': '2.2.2.2', 'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Zune;1;250;', 'event_list': '1'},
        ])
        result, _ = extract_revenue_data(df)
        self.assertEqual(len(result), 2)
        domains = set(result['Search Engine Domain'].tolist())
        self.assertEqual(domains, {'google.com', 'bing.com'})

    def test_dates_set_populated(self):
        """The dates set should contain the date of purchase hits."""
        df = make_dataframe([
            {'ip': '1.1.1.1', 'referrer': 'http://www.google.com/search?q=Ipod'},
            {'ip': '1.1.1.1', 'date_time': '2009-09-27 07:07:40',
             'referrer': 'http://www.esshopzilla.com/cart/',
             'product_list': 'Electronics;Ipod;1;290;', 'event_list': '1'},
        ])
        _, dates = extract_revenue_data(df)
        self.assertIn('2009-09-27', dates)

    def test_empty_dataframe_returns_empty(self):
        """An empty input should return an empty dataframe gracefully."""
        df = make_dataframe([])
        result, dates = extract_revenue_data(df)
        self.assertEqual(len(result), 0)
        self.assertEqual(len(dates), 0)

    def test_full_sample_file(self):
        """End-to-end test against the actual provided data file."""
        import os
        path = '/mnt/user-data/uploads/data_36_.sql'
        if not os.path.exists(path):
            self.skipTest("Sample file not available")

        data = pd.read_csv(path, sep='\t', encoding='utf-8-sig')
        result, dates = extract_revenue_data(data)

        # Should have 2 rows: google/ipod and bing/zune
        self.assertEqual(len(result), 2)

        # Sorted descending — google ipod ($480) should be first
        self.assertEqual(result.iloc[0]['Search Engine Domain'], 'google.com')
        self.assertEqual(result.iloc[0]['Search Keyword'], 'ipod')
        self.assertAlmostEqual(result.iloc[0]['Revenue'], 480.0)

        self.assertEqual(result.iloc[1]['Search Engine Domain'], 'bing.com')
        self.assertAlmostEqual(result.iloc[1]['Revenue'], 250.0)

        # Total revenue
        self.assertAlmostEqual(result['Revenue'].sum(), 730.0)

        # Date should be detected
        self.assertIn('2009-09-27', dates)


if __name__ == '__main__':
    unittest.main(verbosity=2)