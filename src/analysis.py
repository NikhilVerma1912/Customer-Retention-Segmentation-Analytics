"""Reproducible customer segmentation and retention-indicator analysis."""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/Dataset.csv'
PROCESSED = ROOT / 'data/processed'
FIGURES = ROOT / 'reports/figures'
REPORTS = ROOT / 'reports'
FREQUENCY = {'Weekly': 52, 'Fortnightly': 26, 'Bi-Weekly': 26, 'Monthly': 12,
             'Every 3 Months': 4, 'Quarterly': 4, 'Annually': 1}

def run():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RAW)
    df.columns = df.columns.str.strip().str.lower().str.replace(r'[^a-z0-9]+', '_', regex=True).str.strip('_')
    df = df.drop_duplicates().copy()
    df['review_rating'] = pd.to_numeric(df['review_rating'], errors='coerce')
    df['review_rating'] = df['review_rating'].fillna(df['review_rating'].median())
    df['purchase_amount_usd'] = pd.to_numeric(df['purchase_amount_usd'], errors='coerce')
    df['previous_purchases'] = pd.to_numeric(df['previous_purchases'], errors='coerce')
    df['annualized_frequency_proxy'] = df['frequency_of_purchases'].map(FREQUENCY)
    if df['annualized_frequency_proxy'].isna().any():
        raise ValueError('Unmapped frequency categories: ' + str(df.loc[df['annualized_frequency_proxy'].isna(), 'frequency_of_purchases'].unique()))
    # Quartile-based behavioral scoring: each dimension scores 1–4.
    # Rank(method='first') avoids qcut failing on tied values; deterministic by row order.
    for source, target in [('purchase_amount_usd','spend_score'), ('previous_purchases','history_score'),
                           ('annualized_frequency_proxy','frequency_score')]:
        df[target] = pd.qcut(df[source].rank(method='first'), 4, labels=[1,2,3,4]).astype(int)
    df['engagement_score'] = df[['spend_score','history_score','frequency_score']].sum(axis=1)
    df['segment'] = pd.cut(df['engagement_score'], bins=[2,5,8,12],
                           labels=['Low engagement','Developing','High engagement'], include_lowest=True)
    df['subscription_flag'] = df['subscription_status'].eq('Yes').astype(int)
    df.to_csv(PROCESSED / 'customers_cleaned_segmented.csv', index=False)
    segment = df.groupby('segment', observed=True).agg(customers=('customer_id','size'),
        avg_purchase_usd=('purchase_amount_usd','mean'), avg_previous_purchases=('previous_purchases','mean'),
        subscription_rate=('subscription_flag','mean'), avg_engagement_score=('engagement_score','mean')).reset_index()
    segment.to_csv(PROCESSED / 'segment_summary.csv', index=False)
    category = df.groupby('category').agg(customers=('customer_id','size'),
                total_spend_usd=('purchase_amount_usd','sum')).reset_index().sort_values('customers', ascending=False)
    category.to_csv(PROCESSED / 'category_summary.csv', index=False)
    def chart(name):
        plt.tight_layout(); plt.savefig(FIGURES / name, dpi=160, bbox_inches='tight'); plt.close()
    plt.figure(figsize=(8,5)); plt.bar(category['category'],category['customers']);plt.title('Customers by Product Category');plt.ylabel('Customers');chart('category_customers.png')
    plt.figure(figsize=(8,5)); plt.hist(df['purchase_amount_usd'],bins=20);plt.title('Purchase Amount Distribution');plt.xlabel('Purchase Amount (USD)');plt.ylabel('Customers');chart('purchase_distribution.png')
    plt.figure(figsize=(8,5)); plt.bar(segment['segment'].astype(str),segment['customers']);plt.title('Customer Engagement Segments');plt.ylabel('Customers');chart('segment_sizes.png')
    plt.figure(figsize=(8,5)); plt.bar(segment['segment'].astype(str),segment['subscription_rate']*100);plt.title('Subscription Rate by Segment');plt.ylabel('Subscription rate (%)');chart('segment_subscription.png')
    metrics = {'customers':len(df),'total_observed_purchase_usd':df['purchase_amount_usd'].sum(),
        'average_observed_purchase_usd':df['purchase_amount_usd'].mean(),
        'subscription_rate':df['subscription_flag'].mean(),
        'missing_review_ratings_in_raw':int(pd.read_csv(RAW)['Review Rating'].isna().sum())}
    lines = ['# Analysis Findings', '', '## Dataset metrics', ''] + [f'- **{k.replace("_"," ").title()}:** {v:,.2f}' for k,v in metrics.items()]
    lines += ['', '## Segment summary', '', segment.to_markdown(index=False, floatfmt='.2f'), '',
      '## Interpretation and limitations', '',
      '- Each row is one customer with one observed purchase amount. Summing this field is the sum of recorded amounts, **not customer lifetime revenue**.',
      '- Engagement segments are rule-based descriptive groups, not validated predictions of churn.',
      '- Previous purchases and reported frequency are proxies for engagement; the data has no transaction dates, last purchase dates, or observation windows.',
      '- **Actual retention rate, churn rate, cohort analysis, and RFM recency cannot be calculated** from this dataset.',
      '- Annualized frequency is an ordinal-like proxy from reported labels, not verified annual transaction counts.',
      '- Segmentation uses row-order tie breaking in quartiles, which can separate customers with equal source values.',
      '', '## Suggested actions', '',
      '- High engagement: prioritize loyalty recognition and tailored offers.',
      '- Developing: test targeted cross-sell and subscription messaging.',
      '- Low engagement: test re-engagement campaigns; do not label these customers as confirmed churned.',
      '', '## Visualizations', '',
      '![Customer segments](figures/segment_sizes.png)', '',
      '![Subscription by segment](figures/segment_subscription.png)', '',
      '![Category customers](figures/category_customers.png)', '',
      '![Purchase distribution](figures/purchase_distribution.png)', '']
    (REPORTS/'findings.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Analysis complete. Outputs saved to data/processed and reports/.')
    print(segment.to_string(index=False))
if __name__ == '__main__': run()

