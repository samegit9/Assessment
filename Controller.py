import pandas as pd
import re
from datetime import datetime
# import matplotlib.pyplot as plt

# Maps each search engine domain to the query parameter that holds the keyword
DOMAIN_KEY_MAP = {
    'google.com': 'q',
    'yahoo.com':  'p',
    'bing.com':   'q',
}


class DataExtractor:
    def __init__(self, data: pd.DataFrame):
        """Initialize the DataExtractor with the dataframe."""
        self.data = data.fillna('')

    def extract_domain_and_keyword(self, referrer: str):
        """Pull the search engine domain and keyword out of a referrer URL."""
        try:
            match = re.search(r"(?<=://)(?:www\.)?([A-Za-z0-9\-\.]+\.[A-Za-z]{2,3})", referrer)
            if not match:
                return None, None

            domain = '.'.join(match.group(1).split('.')[-2:])

            if domain not in DOMAIN_KEY_MAP:
                return None, None

            param = DOMAIN_KEY_MAP[domain]
            kw_match = re.search(param + r'=([^\&\/]+)', referrer)
            if not kw_match:
                return None, None

            keyword = kw_match.group(1).replace('+', ' ')
            return domain, keyword

        except Exception:
            return None, None

    def extract_revenue(self, row: dict):
        """Return revenue if this hit is a purchase event, otherwise 0."""
        if not row.get('product_list'):
            return 0.0

        fields = row['product_list'].split(';')
        if len(fields) < 4 or not fields[3]:
            return 0.0

        event_list = str(row.get('event_list', '')).replace('.0', '')
        if '1' not in event_list.split(','):
            return 0.0

        try:
            return float(fields[3])
        except ValueError:
            return 0.0

    def format_date(self, date_time: str):
        """Convert date string to YYYY-mm-dd format."""
        try:
            return datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except ValueError:
            return date_time

    # def plot_revenue(self, df: pd.DataFrame):
    #     """Bar chart of mean revenue by search keyword."""
    #     filtered_df = df.groupby('Search Keyword')['Revenue'].mean()
    #     filtered_df.plot(kind='bar')
    #     plt.title('Mean Revenue by Search Keyword')
    #     plt.xlabel('Search Keyword')
    #     plt.ylabel('Mean Revenue')
    #     plt.tight_layout()
    #     plt.show()

    def extract_revenue_data(self):
        """
        Process self.data and return:
          - df:    Search Engine Domain | Search Keyword | Revenue | date
          - dates: set of date strings found in purchase hits
        """
        # Pass 1: find the first search engine referrer for each IP
        session_referrers = {}
        for _, row in self.data.iterrows():
            ip = row['ip']
            if ip in session_referrers:
                continue
            domain, keyword = self.extract_domain_and_keyword(row['referrer'])
            if domain and keyword:
                session_referrers[ip] = (domain, keyword)

        # Pass 2: find purchase rows and attribute revenue to the session referrer
        results = []
        dates = set()

        for _, row in self.data.iterrows():
            revenue = self.extract_revenue(row)
            if revenue == 0.0:
                continue

            ip = row['ip']
            if ip not in session_referrers:
                continue

            domain, keyword = session_referrers[ip]
            date_str = self.format_date(row['date_time'])
            dates.add(date_str)

            results.append({
                'Search Engine Domain': domain,
                'Search Keyword':       keyword,
                'Revenue':              revenue,
                'date':                 date_str,
            })

        df = pd.DataFrame(results, columns=['Search Engine Domain', 'Search Keyword', 'Revenue', 'date'])

        # Group by domain + keyword and sum revenue
        df = (
            df.groupby(['Search Engine Domain', 'Search Keyword', 'date'], as_index=False)
              .agg({'Revenue': 'sum'})
              .sort_values('Revenue', ascending=False)
              .reset_index(drop=True)
        )

        return df, dates