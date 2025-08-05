import streamlit as st
import pandas as pd
import numpy as np
import requests

# Page configuration
st.set_page_config(
    page_title="Adjusted Fully Diluted Value (FDV) Calculator",
    page_icon="📈",
    layout="wide"
)

st.title("Adjusted Fully Diluted Value (FDV) Calculator")

# Add some visual styling to make the description stand out
st.markdown("""
<div style="
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 50%, #e8edf2 100%); 
    padding: 25px; 
    border-radius: 15px; 
    margin: 20px 0;
    box-shadow: 0 6px 20px rgba(108, 117, 125, 0.2);
    border: 1px solid rgba(108, 117, 125, 0.15);
">
    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #495057; font-weight: 500;">
        There's been growing <a href="https://www.ar.ca/blog/fixing-token-valuations-arca-proposes-adjusted-market-cap-standard" target="_blank" style="color: #6c757d; text-decoration: underline; text-decoration-color: rgba(108, 117, 125, 0.5);">recognition</a> across the market that traditional FDV metrics fall short and new market standards are needed. At <strong><a href="https://www.unsupervised.capital/" target="_blank" style="color: #495057; text-decoration: underline; text-decoration-color: rgba(73, 80, 87, 0.5);">Unsupervised Capital</a></strong>, we agree, and have developed a valuation <a href="https://www.unsupervised.capital/writing/reframing-subnet-valuation" target="_blank" style="color: #6c757d; text-decoration: underline; text-decoration-color: rgba(108, 117, 125, 0.5);">framework</a> tailored specifically to Bittensor subnet tokens.
    </p>
    <br>
    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #495057; font-weight: 500;">
        Using this framework, we adjust the FDV based on two critical factors: our expected holding period and the impact of staking rewards over that holding period. The outcome is an adjusted FDV that uses the projected circulating supply of tokens at the end of the expected holding period, and also accounts for how staking rewards effectively reduce the cost basis by increasing token holdings for the same initial investment.
    </p>
</div>
""", unsafe_allow_html=True)

def fetch_subnet_data(subnet_id, api_key):
    """
    Fetch current circulating supply for a given subnet ID
    """
    try:
        headers = {
            'accept': 'application/json',
            'X-API-Key': api_key
        }
        
        response = requests.get('https://api.tao.app/api/beta/subnet_screener', headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Find the subnet with matching netuid
        for subnet in data:
            if subnet['netuid'] == int(subnet_id):
                return subnet['alpha_circ']
        
        return None
        
    except Exception as e:
        st.error(f"Error fetching subnet data: {str(e)}")
        return None

def fetch_fdv_data(subnet_id, api_key):
    """
    Fetch current FDV in USD for a given subnet ID
    """
    try:
        headers = {
            'accept': 'application/json',
            'X-API-Key': api_key
        }
        
        url = f'https://api.tao.app/api/beta/analytics/subnets/valuation?netuid={subnet_id}&page=1&page_size=100'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Get the latest (first) entry
        if data['data'] and len(data['data']) > 0:
            return data['data'][0]['alpha_fdv_usd']
        
        return None
        
    except Exception as e:
        st.error(f"Error fetching FDV data: {str(e)}")
        return None

def calculate_alpha_growth(subnet_id, initial_holdings, weeks, start_alpha_supply,
                          alpha_injection_param, alpha_in_pool_param, avg_root_staked_tao):
    """
    Calculate Alpha token growth over time based on staking rewards.
    """
    current_holdings = initial_holdings
    weekly_data = []

    for week in range(weeks):
        # Start of Period Total Alpha Supply
        start_total_supply = start_alpha_supply if week == 0 else end_total_supply

        # End of Period Total Alpha Supply
        end_total_supply = start_total_supply + 7200*7 + 7200*7*alpha_injection_param

        # Start of Period Alpha Out Supply
        start_out_supply = start_total_supply * (1 - alpha_in_pool_param)

        # End of Period Alpha Out Supply
        end_out_supply = end_total_supply * (1 - alpha_in_pool_param)

        # Average Alpha Out Supply
        avg_out_supply = (start_out_supply + end_out_supply) / 2

        # Start of Period Root Proportion
        start_root_proportion = (avg_root_staked_tao * 0.18) / (avg_root_staked_tao * 0.18 + start_total_supply)

        # Start of Period Alpha Proportion
        start_alpha_proportion = 1 - start_root_proportion

        # End of Period Root Proportion
        end_root_proportion = (avg_root_staked_tao * 0.18) / (avg_root_staked_tao * 0.18 + end_total_supply)

        # End of Period Alpha Proportion
        end_alpha_proportion = 1 - end_root_proportion

        # Period Average Alpha Proportion
        period_avg_alpha_proportion = (start_alpha_proportion + end_alpha_proportion) / 2

        # Period Alpha Proportion Adjusted Alpha Staking Rewards
        period_staking_rewards = (end_out_supply - start_out_supply) * 0.41 * period_avg_alpha_proportion

        # Alpha Staking Rewards for user
        user_staking_rewards = (current_holdings / avg_out_supply) * period_staking_rewards

        # Alpha Holdings (After Staking Rewards)
        new_holdings = current_holdings + user_staking_rewards

        # Alpha APR
        alpha_apr = user_staking_rewards / current_holdings if current_holdings > 0 else 0

        # APY
        apy = alpha_apr * 52

        # Store weekly data
        weekly_data.append({
            'Week': week + 1,
            'Start_Holdings': current_holdings,
            'Staking_Rewards': user_staking_rewards,
            'End_Holdings': new_holdings,
            'Weekly_APR': alpha_apr,
            'Annualized_APY': apy
        })

        # Update holdings for next week
        current_holdings = new_holdings
        start_alpha_supply = end_total_supply

    return {
        'subnet_id': subnet_id,
        'initial_holdings': initial_holdings,
        'final_holdings': current_holdings,
        'weeks_analyzed': weeks,
        'total_rewards': current_holdings - initial_holdings,
        'weekly_data': weekly_data
    }

# Input Section
st.header("Input Parameters")

col1, col2 = st.columns(2)

with col1:
    subnet_id = st.text_input("Subnet ID", value="1")
    initial_holdings = st.number_input("Initial Alpha Holdings", value=5000.0, min_value=0.0, step=100.0)
    tao_investment = st.number_input("TAO Investment", value=100.0, min_value=0.0, step=10.0)

with col2:
    weeks = st.number_input("Analysis Period (weeks)", value=52, min_value=1, max_value=520, step=1)

# API Key or Manual Data Entry
st.subheader("Data Source")
data_source = st.radio(
    "Choose how to get subnet data:",
    ["Use API (requires tao.app API key)", "Enter data manually"],
    help="If you have a tao.app API key, choose the first option for automatic data fetching. Otherwise, enter the data manually."
)

if data_source == "Use API (requires tao.app API key)":
    api_key = st.text_input(
        "Enter your TAO API Key", 
        type="password",
        help="Get your API key from tao.app. This will be used to automatically fetch current circulating supply and FDV data."
    )
    if not api_key:
        st.warning("⚠️ Please enter your API key to use automatic data fetching.")
    manual_supply = 1925000.0  # Default value
    manual_fdv = 135000000.0   # Default value
else:
    st.info("💡 You can find current subnet data at tao.app or other Bittensor data sources.")
    col1, col2 = st.columns(2)
    with col1:
        manual_supply = st.number_input("Current Circulating Supply of Alpha", value=1925000.0, min_value=0.0, step=10000.0)
    with col2:
        manual_fdv = st.number_input("Current FDV (in USD)", value=135000000.0, min_value=0.0, step=1000000.0, format="%.0f")
    api_key = None

# Hardcoded optional parameters
alpha_injection_param = 0.75
alpha_in_pool_param = 0.37
avg_root_staked_tao = 5600000.0

# Calculate button
if st.button("Calculate Analysis", type="primary"):
    
    if data_source == "Use API (requires API key)":
        if not api_key:
            st.error("❌ Please enter your API key to use automatic data fetching.")
            st.stop()
            
        # Fetch data from APIs
        with st.spinner("Fetching subnet data..."):
            start_alpha_supply = fetch_subnet_data(subnet_id, api_key)
            current_fdv_usd = fetch_fdv_data(subnet_id, api_key)
        
        if start_alpha_supply is None or current_fdv_usd is None:
            st.error(f"❌ Could not fetch data for Subnet ID {subnet_id}. Please check your API key and subnet ID, or try entering data manually.")
            st.stop()
        else:
            # Display fetched data
            st.success(f"✅ Data fetched successfully!")
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Current Circulating Supply:** {start_alpha_supply:,.0f} Alpha tokens")
            with col2:
                st.info(f"**Current FDV:** ${current_fdv_usd:,.0f}")
    else:  # data_source == "Enter data manually"
        # Use manual data
        start_alpha_supply = manual_supply
        current_fdv_usd = manual_fdv
        st.success("✅ Using manual data!")
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Current Circulating Supply:** {start_alpha_supply:,.0f} Alpha tokens")
        with col2:
            st.info(f"**Current FDV:** ${current_fdv_usd:,.0f}")
    
    # Run analysis
    with st.spinner("Running analysis..."):
        results = calculate_alpha_growth(
            subnet_id=subnet_id,
            initial_holdings=initial_holdings,
            weeks=weeks,
            start_alpha_supply=start_alpha_supply,
            alpha_injection_param=alpha_injection_param,
            alpha_in_pool_param=alpha_in_pool_param,
            avg_root_staked_tao=avg_root_staked_tao
        )

    # Calculate all metrics upfront
    # Cost basis calculations
    initial_cost_basis = tao_investment / initial_holdings
    adjusted_cost_basis = tao_investment / results['final_holdings']
    cost_basis_decrease = ((initial_cost_basis - adjusted_cost_basis) / initial_cost_basis) * 100

    # FDV calculations
    max_supply = 21_000_000
    final_circulating_supply = start_alpha_supply + (weeks * (7200*7 + 7200*7*alpha_injection_param))
    circulating_supply_percentage = (final_circulating_supply / max_supply) * 100
    fdv_multiplier = final_circulating_supply / max_supply
    supply_discount = (1 - fdv_multiplier) * 100
    staking_discount = cost_basis_decrease
    effective_fdv_multiplier = fdv_multiplier * (1 - (cost_basis_decrease / 100))
    total_effective_discount = (1 - effective_fdv_multiplier) * 100
    adjusted_fdv_usd = current_fdv_usd * (1 - (total_effective_discount / 100))

    # Store results in session state
    st.session_state.results = results
    st.session_state.current_fdv_usd = current_fdv_usd
    st.session_state.total_effective_discount = total_effective_discount
    st.session_state.adjusted_fdv_usd = adjusted_fdv_usd
    st.session_state.initial_cost_basis = initial_cost_basis
    st.session_state.adjusted_cost_basis = adjusted_cost_basis
    st.session_state.cost_basis_decrease = cost_basis_decrease
    st.session_state.final_circulating_supply = final_circulating_supply
    st.session_state.circulating_supply_percentage = circulating_supply_percentage
    st.session_state.supply_discount = supply_discount
    st.session_state.staking_discount = staking_discount

# Display results if they exist
if 'results' in st.session_state:
    st.markdown("---")
    st.header("Adjusted Fully Diluted Valuation",
              help="Shows the resulting adjusted valuation based on the projected circulating supply at the end of the analysis period and staking reward benefits.",
              divider="blue",
              width="stretch")
    
    # Center the single metric
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        st.metric("Adjusted FDV", f"${st.session_state.adjusted_fdv_usd:,.0f}", border=True)

    st.markdown("")
    st.markdown("---")
    st.header("Staking Reward Analysis",
                 help="Shows how your Alpha holdings grow through staking rewards and how this reduces your effective cost basis per token. The adjusted cost basis divides the initial TAO investment by the final Alpha holdings. ",
                 divider="blue",
                width="content")
    
    # First row - Holdings and Rewards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Initial Alpha Holdings", f"{st.session_state.results['initial_holdings']:,.2f}")
    
    with col2:
        st.metric("Final Alpha Holdings", f"{st.session_state.results['final_holdings']:,.2f}", delta=f"{((st.session_state.results['final_holdings'] / st.session_state.results['initial_holdings']) - 1) * 100:.2f}%")
    
    with col3:
        st.metric("Total Rewards Earned", f"{st.session_state.results['total_rewards']:,.2f}")

    # Second row - Cost Basis
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Initial Cost Basis", f"{st.session_state.initial_cost_basis:.4f} TAO per Alpha")
    
    with col2:
        st.metric("Adjusted Cost Basis", f"{st.session_state.adjusted_cost_basis:.4f} TAO per Alpha")
    
    with col3:
        st.metric("Cost Basis Decrease", f"{st.session_state.cost_basis_decrease:.2f}%")

    st.markdown("")
    st.markdown("---")
    st.header("Adjusted Fully Diluted Valuation (FDV) Analysis",
              help="Detailed breakdown showing projected circulating supply, staking yield effects, and how they combine to create the total effective discount to traditional FDV.",
              divider="blue",
              width="content")
    
    # First row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Final Circulating Supply", f"{st.session_state.final_circulating_supply:,.0f} Alpha")
    
    with col2:
        st.metric("% of Max Supply (21M)", f"{st.session_state.circulating_supply_percentage:.1f}%")
    
    with col3:
        st.metric("FDV Discount", f"{st.session_state.supply_discount:.1f}%")
    
    # Second row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Staking Yield Discount (Cost Basis Decrease)", f"{st.session_state.staking_discount:.1f}%")
    
    with col2:
        st.metric("FDV Discount", f"{st.session_state.supply_discount:.1f}%")
    
    with col3:
        st.metric("Total Effective Discount to FDV", f"{st.session_state.total_effective_discount:.1f}%")

    # Weekly breakdown toggle
    st.markdown("")
    st.markdown("---")
    if st.checkbox("Show Weekly Breakdown"):
        st.markdown("<h3 style='color: #2c3e50; margin: 20px 0;'>Weekly Breakdown</h3>", unsafe_allow_html=True)
        df = pd.DataFrame(st.session_state.results['weekly_data'])
        df['Start_Holdings'] = df['Start_Holdings'].round(2)
        df['Staking_Rewards'] = df['Staking_Rewards'].round(4)
        df['End_Holdings'] = df['End_Holdings'].round(2)
        df['Weekly_APR'] = (df['Weekly_APR'] * 100).round(4)
        df['Annualized_APY'] = (df['Annualized_APY'] * 100).round(2)
        
        st.dataframe(df, use_container_width=True)

# Information sidebar
with st.sidebar:
    st.header("About This Calculator")
    st.markdown("""
    This calculator helps you understand the true value proposition of Alpha token staking by showing:
    
    **Token Growth**: How your holdings compound through staking rewards
    
    **Cost Basis Reduction**: How staking effectively reduces your entry price
    
    **Effective Valuation**: Your real discount to FDV when accounting for realistic circulating supply and staking benefits
    
    The analysis runs weekly calculations to show compound growth over your specified timeframe.
    """)
    
    st.header("Assumptions")
    st.markdown("""
    This is a simple calculator with multiple assumptions made for ease of calculation. We open sourced the tool so people can fork it and improve/adjust it as needed. These are the primary assumptions:
    
    * Root TAO remains fixed at 5.6M
    * Alpha injected into the pool is fixed at 0.75. Onchain, this value is dynamic and can fluctuate between 0 and 1.
    * The ratio between Alpha in the pool and Alpha held outside the pool is 0.37.
    * We're not including any validator take rates.
    
    Feel free to fork this code and update these assumptions as needed.
    """)