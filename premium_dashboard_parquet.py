import streamlit as st
import pandas as pd

import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="Olist Business Intelligence", layout="wide", initial_sidebar_state="expanded")

# 2. Premium Styling
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stMetric { 
        background: rgba(255, 255, 255, 0.05); 
        padding: 20px !important; 
        border-radius: 12px; 
        border: 1px solid rgba(88, 166, 255, 0.2);
        transition: all 0.3s ease;
        min-height: 160px; /* 고정 높이 확보 */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .stMetric:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: #58a6ff;
        transform: translateY(-5px);
    }
    [data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow-wrap: break-word !important;
        min-height: 3.5em; /* 라벨 영역 높이 고정 */
        line-height: 1.3;
        color: #8b949e !important;
        font-size: 0.95rem !important;
        display: flex;
        align-items: center;
    }
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        color: #58a6ff !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.9rem !important;
    }
    h1, h2, h3 { color: #58a6ff; font-family: 'Segoe UI', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data_from_parquet():
    try:
        df = pd.read_parquet('olist_consolidated.parquet')
    except Exception:
        st.error("Parquet file not found. Please run convert_to_parquet.py first.")
        return pd.DataFrame() # Return empty to avoid crash
    
    # Date conversion
    date_cols = ['order_purchase_timestamp', 'order_delivered_customer_date', 
                 'order_approved_at', 'order_delivered_carrier_date']
    for col in date_cols:
        df[col] = pd.to_datetime(df[col])

    # Filter for delivered orders (consistent with previous view)
    df = df.dropna(subset=['order_delivered_customer_date'])

    # Calculate delivery days
    df['delivery_days'] = (df['order_delivered_customer_date'] - df['order_purchase_timestamp']).dt.days
    
    return df

def calculate_dynamic_thresholds(df):
    # IQR Method for Freight
    f_q1 = df['freight_value'].quantile(0.25)
    f_q3 = df['freight_value'].quantile(0.75)
    f_limit = f_q3 + 1.5 * (f_q3 - f_q1)
    f_warning = f_limit * 0.8
    
    # IQR Method for Delivery Days
    d_q1 = df['delivery_days'].quantile(0.25)
    d_q3 = df['delivery_days'].quantile(0.75)
    d_limit = d_q3 + 1.5 * (d_q3 - d_q1)
    d_warning = d_limit * 0.8
    
    return f_limit, d_limit, f_warning, d_warning

def main():
    st.title("Olist Dynamic BI Dashboard")
    st.write("자동 갱신되는 데이터와 동적 이상치 임계값을 반영한 비즈니스 리포트")

    df = load_data_from_parquet()
    
    if df.empty:
        st.warning("데이터를 불러올 수 없습니다.")
        return

    f_limit, d_limit, f_warning, d_warning = calculate_dynamic_thresholds(df)

    # Sidebar Filter
    st.sidebar.header("Data Coverage & Filters")
    
    # Display Data Period
    min_date = df['order_purchase_timestamp'].min().date()
    max_date = df['order_purchase_timestamp'].max().date()
    st.sidebar.info(f"📅 분석 기간:\n{min_date} ~ {max_date}")
    
    # Check if customer_state exists (it should be in consolidated)
    if 'customer_state' in df.columns:
        state_options = df['customer_state'].unique()
        default_options = state_options[:5] if len(state_options) > 0 else []
        selected_state = st.sidebar.multiselect("Select State", options=state_options, default=default_options)
        
        if selected_state:
            plot_df = df[df['customer_state'].isin(selected_state)]
        else:
            plot_df = df
    else:
        plot_df = df

    # --- KPI Section (Two Rows to avoid text cutoff) ---
    st.markdown("### 주요 요약 지표 (Summary Metrics)")
    row1_c1, row1_c2, row1_c3 = st.columns(3)
    with row1_c1:
        st.metric("Total Revenue (누적 매출액)", f"R$ {plot_df['price'].sum():,.0f}", delta="Premium")
    with row1_c2:
        st.metric("Avg Satisfaction (평균 만족도)", f"{plot_df['review_score'].mean():.2f} / 5.0")
    with row1_c3:
        st.metric("Avg Delivery (평균 배송일)", f"{plot_df['delivery_days'].mean():.1f} Days")

    st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True) # Spacer

    row2_c1, row2_c2, row2_c3 = st.columns(3)
    with row2_c1:
        at_risk_cnt = len(plot_df[((plot_df['delivery_days'] > d_warning) & (plot_df['delivery_days'] <= d_limit)) | 
                                 ((plot_df['freight_value'] > f_warning) & (plot_df['freight_value'] <= f_limit))])
        st.metric("At-Risk Orders (관리 필요 주문)", f"{at_risk_cnt:,}", delta="Warning", delta_color="off")
    with row2_c2:
        worst_case_cnt = len(plot_df[(plot_df['delivery_days'] > d_limit) & (plot_df['freight_value'] > f_limit)])
        st.metric("Worst Case (최악 지연 사례)", f"{worst_case_cnt:,}", delta="Critical", delta_color="inverse")
    with row2_c3:
        total_orders = len(plot_df)
        st.metric("Total Orders (전체 주문 수)", f"{total_orders:,}")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Business Overview", "⚙️ Operational Trend", "⚠️ Outlier Deep Dive", "🌟 Satisfaction Analysis"])

    with tab1:
        # (Existing Business Overview content remains)
        c1, c2 = st.columns(2)
        with c1:
            # Revenue Trend
            monthly_sales = plot_df.set_index('order_purchase_timestamp').resample('M')['price'].sum().reset_index()
            fig_rev = px.line(monthly_sales, x='order_purchase_timestamp', y='price', title="Monthly Revenue Growth", template="plotly_dark")
            fig_rev.update_traces(line_color='#58a6ff', fill='tozeroy')
            st.plotly_chart(fig_rev, use_container_width=True)
        with c2:
            # Category Distribution
            if 'product_category_name' in plot_df.columns:
                top_cats = plot_df.groupby('product_category_name')['price'].sum().nlargest(10).reset_index()
                fig_cat = px.bar(top_cats, x='price', y='product_category_name', orientation='h', title="Top 10 Categories", template="plotly_dark", color='price', color_continuous_scale='Blues')
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.warning("Category data not available")

    with tab2:
        st.subheader("Process Lead Time Analysis")
        
        # Operational Metrics using Pandas
        # Filter for valid dates
        op_df = df.dropna(subset=['order_approved_at', 'order_delivered_carrier_date', 'order_delivered_customer_date']).copy()
        
        # Calculate stages
        op_df['p_to_a'] = (op_df['order_approved_at'] - op_df['order_purchase_timestamp']).dt.total_seconds() / 86400
        op_df['a_to_c'] = (op_df['order_delivered_carrier_date'] - op_df['order_approved_at']).dt.total_seconds() / 86400
        op_df['c_to_d'] = (op_df['order_delivered_customer_date'] - op_df['order_delivered_carrier_date']).dt.total_seconds() / 86400
        
        op_df['month'] = op_df['order_purchase_timestamp'].dt.strftime('%Y-%m')
        
        df_perf = op_df.groupby('month')[['p_to_a', 'a_to_c', 'c_to_d']].mean().reset_index()

        fig_perf = px.bar(df_perf, x='month', y=['p_to_a', 'a_to_c', 'c_to_d'], 
                          title="Stacked Lead Time by Process Stage (Days)",
                          labels={'value': 'Days', 'variable': 'Process Stage'},
                          template="plotly_dark",
                          color_discrete_sequence=px.colors.sequential.Viridis)
        
        # Rename traces
        new_names = {'p_to_a': 'Purchase -> Approved', 'a_to_c': 'Approved -> Carrier', 'c_to_d': 'Carrier -> Delivered'}
        fig_perf.for_each_trace(lambda t: t.update(name = new_names.get(t.name, t.name)))
        
        st.plotly_chart(fig_perf, use_container_width=True)
        st.write("### 운영 효율성 인사이트")
        st.write("- **상태 확인**: 최근으로 올수록 전체 리드타임이 단축되는 긍정적인 추세를 보입니다.")
        st.write("- **병목 지점**: 'Carrier -> Delivered'(최종 배송) 구간이 전체 소요 시간의 가장 큰 비중을 차지합니다.")
        st.write("- **판매자 관리**: 'Approved -> Carrier' 구간의 변동성은 판매자의 입고 준비 속도를 나타냅니다.")

    with tab3:
        st.subheader("Dynamic Outlier Thresholds")
        st.info(f"현재 데이터 기준 임계치 - 배송비: R$ {f_limit:.2f} | 배송기간: {d_limit:.1f} 일")
        
        c3, c4 = st.columns(2)
        with c3:
            # Delivery Days Dist
            fig_dist = px.histogram(plot_df, x='delivery_days', title="Delivery Days Distribution", template="plotly_dark", color_discrete_sequence=['#58a6ff'])
            fig_dist.add_vline(x=d_limit, line_dash="dash", line_color="red", annotation_text="Limit")
            fig_dist.add_vline(x=d_warning, line_dash="dot", line_color="yellow", annotation_text="Warning")
            st.plotly_chart(fig_dist, use_container_width=True)
        with c4:
            # Freight vs Price Scatter
            fig_scatter = px.scatter(plot_df, x='price', y='freight_value', color='review_score', title="Price vs Freight (Color by Score)", template="plotly_dark")
            fig_scatter.add_hline(y=f_limit, line_dash="dash", line_color="red")
            fig_scatter.add_hline(y=f_warning, line_dash="dot", line_color="yellow")
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 Outlier Detail Search")
        
        # 이상치 데이터 필터링 (배송지연 혹은 고액 배송비)
        outliers_df = plot_df[(plot_df['delivery_days'] > d_limit) | (plot_df['freight_value'] > f_limit)].copy()
        
        if not outliers_df.empty:
            col_search1, col_search2 = st.columns([1, 2])
            with col_search1:
                selected_id = st.selectbox("조회할 Outlier 주문 ID 선택", options=outliers_df['order_id'].unique())
            
            # 선택된 주문 상세 정보 표시
            detail = outliers_df[outliers_df['order_id'] == selected_id].iloc[0]
            
            with col_search2:
                st.write(f"### Order Details: `{selected_id}`")
                d_col1, d_col2, d_col3 = st.columns(3)
                d_col1.metric("Delivery Days", f"{detail['delivery_days']} 일")
                d_col2.metric("Freight Value", f"R$ {detail['freight_value']:.2f}")
                d_col3.metric("Review Score", f"{detail['review_score']} 점")
                
                st.write(f"**Category**: {detail['product_category_name']} | **State**: {detail['customer_state']}")
                st.write(f"**Purchase Date**: {detail['order_purchase_timestamp']}")
            
            st.markdown("#### All Detected Outliers (이상치 전체 목록)")
            st.dataframe(outliers_df, use_container_width=True)
        else:
            st.warning("선택된 필터 조건 내에 이상치 데이터가 없습니다.")

    with tab4:
        # Comparative Analysis
        plot_df['Segment'] = 'Normal'
        # Hierarchical classification - later rules overwrite earlier ones
        plot_df.loc[(plot_df['delivery_days'] > d_warning) | (plot_df['freight_value'] > f_warning), 'Segment'] = 'At-Risk'
        plot_df.loc[plot_df['freight_value'] > f_limit, 'Segment'] = 'High Freight'
        plot_df.loc[plot_df['delivery_days'] > d_limit, 'Segment'] = 'Delayed'
        plot_df.loc[(plot_df['delivery_days'] > d_limit) & (plot_df['freight_value'] > f_limit), 'Segment'] = 'Worst Case'
        
        avg_scores = plot_df.groupby('Segment')['review_score'].mean().reset_index()
        # Sort for consistent display
        avg_scores['sort_idx'] = avg_scores['Segment'].map({'Normal': 0, 'At-Risk': 1, 'High Freight': 2, 'Delayed': 3, 'Worst Case': 4})
        avg_scores = avg_scores.sort_values('sort_idx')

        fig_score = px.bar(avg_scores, x='Segment', y='review_score', color='Segment', 
                           title="Satisfaction Score by Segment", template="plotly_dark",
                           color_discrete_map={
                               'Normal': '#28a745', 
                               'At-Risk': '#17a2b8', 
                               'High Freight': '#6f42c1', 
                               'Delayed': '#ffc107', 
                               'Worst Case': '#dc3545'
                           })
        st.plotly_chart(fig_score, use_container_width=True)
        
        st.write("### Segment Definitions")
        col_inf1, col_inf2 = st.columns(2)
        with col_inf1:
            st.write("- **Normal**: 배송 및 배송비가 통계적 정상 범위 내에 있음")
            st.write("- **At-Risk**: 임계값의 80~100% 사이로 주의가 필요한 주문")
            st.write("- **High Freight**: 배송비가 이상치 수준으로 높음")
        with col_inf2:
            st.write("- **Delayed**: 배송 기간이 이상치 수준으로 늦음 (평점 하락 주원인)")
            st.write("- **Worst Case**: 고액 배송비 + 배송 지연이 동시에 발생한 최악의 사례")

if __name__ == "__main__":
    main()
