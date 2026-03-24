import streamlit as st
import pandas as pd
import random
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# --- STREAMLIT UI SETUP & CSS ---
st.set_page_config(layout="wide", page_title="Trading Simulator")

# Inject AGGRESSIVE CSS to reduce whitespace everywhere
st.markdown("""
    <style>
        /* --- SIDEBAR TWEAKS (Keep existing) --- */
        section[data-testid="stSidebar"] .block-container {
            padding-top: 0rem !important;
            margin-top: -2rem !important;
        }
        [data-testid="stSidebar"] h3 {
            margin-top: 0rem !important;
            padding-top: 0rem !important;
            margin-bottom: 0.5rem !important;
        }
        [data-testid="stSidebar"] .stButton {
            margin-top: -5px !important;
        }
        [data-testid="stSidebar"] .stElementContainer {
            margin-bottom: -0.5rem !important;
        }

        /* --- MAIN CONTENT COMPACT TWEAKS --- */
        /* Reduce top padding of main area */
        .main .block-container {
            padding-top: 2rem !important; 
        }
        
        /* Reduce gaps between vertical blocks in main area */
        .main [data-testid="stVerticalBlock"] > div {
            gap: 0.5rem !important; /* Force smaller gap between rows */
        }
        
        /* Make metrics look tighter */
        [data-testid="stMetric"] {
            padding: 5px 0px;
        }
        
        /* Reduce header margins in main area */
        .main h3 {
            padding-top: 0.2rem !important;
            padding-bottom: 0.1rem !important;
            margin-top: 0rem !important;
            margin-bottom: 0rem !important;
            font-size: 1.3rem !important; /* Make headers slightly smaller */
        }
        
        /* Reduce spacing for h5 (section headers) */
        .main h5 {
            padding-top: 0.3rem !important;
            padding-bottom: 0.2rem !important;
            margin-top: 0.3rem !important;
            margin-bottom: 0.2rem !important;
        }
        
        /* Reduce horizontal rule spacing */
        .main hr {
            margin-top: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Leveraged Trading Strategy Simulator")

# --- Core Simulation Logic ---
def simulate_trading_detailed(
    starting_balance,
    risk_percent,
    win_rate_percent,
    stop_loss_percent,
    num_trades,
    leverage,
    maker_fee_percent,
    taker_fee_percent,
    entry_order_type,
    tp_order_type,
    sl_order_type,
    compound_rate_percent,
    win_rate_logic,
    tp_targets, 
    loss_fakeout_chance_percent,
    fakeout_logic
):
    current_balance = starting_balance
    balance_history = [starting_balance]
    trade_details = []
    
    # Init trackers
    results = {
        "wins": 0, 
        "losses": 0,
        "fakeout_losses": 0, # NEW: Track fakeouts specifically
        "total_fees_paid": 0.0,
        "total_gross_profit": 0.0,
        "total_gross_loss": 0.0
    }

    # --- Conversions ---
    risk_rate = risk_percent / 100.0
    win_rate = win_rate_percent / 100.0
    sl_multiplier = stop_loss_percent / 100.0
    maker_fee_rate = maker_fee_percent / 100.0
    taker_fee_rate = taker_fee_percent / 100.0
    compound_rate = compound_rate_percent / 100.0
    loss_fakeout_prob = loss_fakeout_chance_percent / 100.0

    # --- Fee Rates ---
    entry_fee_rate = maker_fee_rate if entry_order_type == "Limit (Maker)" else taker_fee_rate
    tp_exit_fee_rate = maker_fee_rate if tp_order_type == "Limit (Maker)" else taker_fee_rate
    sl_exit_fee_rate = maker_fee_rate if sl_order_type == "Limit (Maker)" else taker_fee_rate

    # --- Pre-calculate outcomes for "Exact" mode ---
    pre_determined_outcomes = []
    if win_rate_logic == "🎯 Exact Count (Fixed)":
        total_wins = int(round(num_trades * win_rate))
        total_losses = num_trades - total_wins
        pre_determined_outcomes = ["WIN"] * total_wins + ["LOSS"] * total_losses
        random.shuffle(pre_determined_outcomes)
    
    # --- Pre-calculate fakeout outcomes for "Exact" mode ---
    pre_determined_fakeouts = set()
    if fakeout_logic == "🎯 Exact Count (Fixed)":
        # Calculate expected number of losses
        if win_rate_logic == "🎯 Exact Count (Fixed)":
            expected_losses = num_trades - int(round(num_trades * win_rate))
        else:
            expected_losses = int(num_trades * (1 - win_rate))
        
        # Determine which losses will be fakeouts
        num_fakeouts = int(round(expected_losses * loss_fakeout_prob))
        if expected_losses > 0:
            fakeout_loss_indices = random.sample(range(expected_losses), min(num_fakeouts, expected_losses))
            pre_determined_fakeouts = set(fakeout_loss_indices)
    
    # Track loss counter for exact fakeout logic
    loss_counter = 0

    for i in range(1, num_trades + 1):
        if current_balance <= 0:
            break 

        balance_before_trade = current_balance
        
        # --- COMPOUNDING & RISK SIZING ---
        total_pnl_so_far = balance_before_trade - starting_balance
        compounded_amount = total_pnl_so_far * compound_rate
        active_balance = starting_balance + compounded_amount
        active_balance = max(0.01, active_balance)

        # Apply Risk % to determine how much of the active balance is used as margin
        position_size_basis = active_balance * risk_rate
        position_size_basis = max(0.01, position_size_basis)

        # --- Trade Execution (Entry) ---
        notional_value_open_total = position_size_basis * leverage
        entry_fee = notional_value_open_total * entry_fee_rate

        # --- Determine Win/Loss ---
        is_win = False
        if win_rate_logic == "🎯 Exact Count (Fixed)":
            if (i-1) < len(pre_determined_outcomes):
                is_win = (pre_determined_outcomes[i-1] == "WIN")
            else:
                is_win = random.random() < win_rate
        else:
            is_win = random.random() < win_rate

        # --- Calculate PnL (Partial Close Logic) ---
        gross_pnl = 0.0
        exit_fees = 0.0
        outcome_str = ""

        # Unpack targets 
        tp1_target, tp1_qty = tp_targets[0]
        tp2_target, tp2_qty = tp_targets[1]
        tp3_target, tp3_qty = tp_targets[2]

        # Normalize quantities
        q1 = tp1_qty / 100.0
        q2 = tp2_qty / 100.0
        q3 = tp3_qty / 100.0
        
        total_q = q1 + q2 + q3
        if total_q < 0.99: 
            q3 += (1.0 - total_q)
        elif total_q > 1.01: 
            q1 = q1 / total_q
            q2 = q2 / total_q
            q3 = q3 / total_q

        if is_win:
            outcome_str = "WIN (Full TP)"
            results["wins"] += 1
            
            # --- TP Level 1 ---
            chunk_margin_1 = position_size_basis * q1
            chunk_pnl_1 = chunk_margin_1 * (tp1_target/100.0) * leverage
            chunk_exit_fee_1 = (chunk_margin_1 * leverage + chunk_pnl_1) * tp_exit_fee_rate
            
            # --- TP Level 2 ---
            chunk_margin_2 = position_size_basis * q2
            chunk_pnl_2 = chunk_margin_2 * (tp2_target/100.0) * leverage
            chunk_exit_fee_2 = (chunk_margin_2 * leverage + chunk_pnl_2) * tp_exit_fee_rate

            # --- TP Level 3 ---
            chunk_margin_3 = position_size_basis * q3
            chunk_pnl_3 = chunk_margin_3 * (tp3_target/100.0) * leverage
            chunk_exit_fee_3 = (chunk_margin_3 * leverage + chunk_pnl_3) * tp_exit_fee_rate

            gross_pnl = chunk_pnl_1 + chunk_pnl_2 + chunk_pnl_3
            exit_fees = chunk_exit_fee_1 + chunk_exit_fee_2 + chunk_exit_fee_3
            
            results["total_gross_profit"] += gross_pnl

        else:
            # It's a LOSS
            results["losses"] += 1
            
            # Determine if this loss is a fakeout
            is_fakeout = False
            if fakeout_logic == "🎯 Exact Count (Fixed)":
                is_fakeout = loss_counter in pre_determined_fakeouts
            else:
                is_fakeout = random.random() < loss_fakeout_prob
            
            loss_counter += 1  # Increment loss counter

            if is_fakeout:
                results["fakeout_losses"] += 1 # Increment counter
                outcome_str = "LOSS (Fakeout: TP1 -> SL)"
                
                # 1. Hit TP Level 1
                chunk_margin_1 = position_size_basis * q1
                chunk_pnl_1 = chunk_margin_1 * (tp1_target/100.0) * leverage 
                chunk_exit_fee_1 = (chunk_margin_1 * leverage + chunk_pnl_1) * tp_exit_fee_rate
                
                # 2. Remaining position hits SL
                remaining_pct = 1.0 - q1
                chunk_margin_sl = position_size_basis * remaining_pct
                chunk_pnl_sl = - (chunk_margin_sl * sl_multiplier * leverage) 
                
                notional_close_sl = max(0, (chunk_margin_sl * leverage) + chunk_pnl_sl)
                chunk_exit_fee_sl = notional_close_sl * sl_exit_fee_rate

                gross_pnl = chunk_pnl_1 + chunk_pnl_sl 
                exit_fees = chunk_exit_fee_1 + chunk_exit_fee_sl

            else:
                outcome_str = "LOSS (Direct SL)"
                base_loss = position_size_basis * sl_multiplier
                leveraged_loss = base_loss * leverage
                gross_pnl = -leveraged_loss
                
                notional_value_close = max(0, notional_value_open_total - leveraged_loss)
                exit_fees = notional_value_close * sl_exit_fee_rate

            if gross_pnl >= 0:
                results["total_gross_profit"] += gross_pnl 
            else:
                results["total_gross_loss"] += gross_pnl


        total_fee = entry_fee + exit_fees
        net_pnl = gross_pnl - total_fee
        results["total_fees_paid"] += total_fee

        current_balance += net_pnl
        if current_balance < 0: current_balance = 0

        balance_history.append(current_balance)
        
        trade_details.append({
            "Trade #": i,
            "Balance Before": round(balance_before_trade, 2),
            "Margin Used": round(position_size_basis, 2), # Show margin used per trade
            "Outcome": outcome_str,
            "Gross P/L ($)": round(gross_pnl, 2),
            "Total Fee ($)": round(total_fee, 4),
            "Net P/L ($)": round(net_pnl, 2),
            "Balance After": round(current_balance, 2)
        })

    # --- Summary ---
    final_balance = balance_history[-1]
    total_net_pnl = final_balance - starting_balance
    total_return_percent = (total_net_pnl / starting_balance) * 100 if starting_balance > 0 else 0
    num_trades_executed = len(trade_details)
    
    # Calculate Actual Fakeout %
    actual_fakeout_pct = 0
    if results["losses"] > 0:
        actual_fakeout_pct = (results["fakeout_losses"] / results["losses"]) * 100

    summary = {
        "starting_balance": starting_balance,
        "final_balance": round(final_balance, 2),
        "total_net_pnl": round(total_net_pnl, 2),
        "total_return_percent": round(total_return_percent, 2),
        "num_trades_executed": num_trades_executed,
        "wins": results["wins"],
        "losses": results["losses"],
        "fakeout_losses": results["fakeout_losses"], # NEW
        "actual_fakeout_pct": actual_fakeout_pct,   # NEW
        "win_rate_actual_percent": (results["wins"] / num_trades_executed * 100) if num_trades_executed > 0 else 0,
        "total_fees_paid": round(results["total_fees_paid"], 2),
        "total_gross_profit": round(results["total_gross_profit"], 2),
        "total_gross_loss": round(results["total_gross_loss"], 2),
        "balance_history": balance_history
    }

    return summary, pd.DataFrame(trade_details)


# --- Plotting Function ---
def plot_balance_history(balance_history, starting_balance, title="Trading Simulation Balance"):
    if not balance_history:
        return None
    fig, ax = plt.subplots(figsize=(10, 4)) # Height reduced slightly for compactness
    ax.plot(range(len(balance_history)), balance_history, marker='.', linestyle='-', markersize=4, label='Balance')
    ax.axhline(y=starting_balance, color='r', linestyle='--', label=f'Start (${starting_balance:,.2f})')
    ax.set_title(title)
    ax.set_xlabel("Trade Number")
    ax.set_ylabel("Balance (USD)")
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend()
    formatter = mticker.StrMethodFormatter('${x:,.2f}')
    ax.yaxis.set_major_formatter(formatter)
    plt.tight_layout()
    return fig


# --- SIDEBAR (Unchanged structure) ---
st.sidebar.subheader("Run Control") 
run_button = st.sidebar.button("🚀 Run Simulation", type="primary")

st.sidebar.subheader("Simulation Parameters")

win_rate_logic = st.sidebar.radio(
    "Win Rate Logic",
    options=["🎲 Probabilistic (Pure Luck)", "🎯 Exact Count (Fixed)"],
    index=1,
    help="Probabilistic: 60% WR = 60% chance per trade. Exact: 60% WR = Exactly 60 wins out of 100 trades (shuffled)."
)

compound_rate = st.sidebar.slider(
    label="Compounding Rate (%)",
    min_value=0,
    max_value=100,
    value=100,
    step=10,
    format="%d%%",
    help="0% = Fixed Trade Size. 100% = Full Compounding."
)

start_bal = st.sidebar.number_input("Starting Balance (USD)", value=100.0, step=100.0)
risk_percent = st.sidebar.number_input(
    "Margin / Risk per Trade (%)", 
    value=100.0, 
    step=10.0, 
    min_value=1.0, 
    max_value=100.0, 
    help="Percentage of your available balance to allocate as margin for each trade."
)
win_rate = st.sidebar.number_input("Win Rate (%)", value=60.0, step=1.0)
n_trades = st.sidebar.number_input("Number of Trades", value=60, step=1)

# --- Advanced Exit Settings ---
with st.sidebar.expander("🎯 Exit Settings (TP Levels)", expanded=True):
    st.write("**Partial Take Profit Levels**")
    c1, c2 = st.columns(2)
    with c1:
        tp1_p = st.number_input("TP 1: Price %", value=0.0, step=0.1)
        tp2_p = st.number_input("TP 2: Price %", value=0.6, step=0.1)
        tp3_p = st.number_input("TP 3: Price %", value=0.0, step=0.1)
    with c2:
        tp1_q = st.number_input("TP 1: Size %", value=0, step=5)
        tp2_q = st.number_input("TP 2: Size %", value=100, step=5)
        tp3_q = st.number_input("TP 3: Size %", value=0, step=5)
    
    st.caption(f"Total Size to Close: {tp1_q + tp2_q + tp3_q}% (Should be 100%)")
    
    st.write("**Stop Loss Behavior**")
    sl_perc = st.number_input("Stop Loss Distance (%)", value=0.3, step=0.1)
    
    fakeout_logic = st.radio(
        "Fakeout Logic",
        options=["🎲 Probabilistic (Random)", "🎯 Exact Count (Fixed)"],
        index=0,
        help="Probabilistic: Each losing trade has X% chance of fakeout. Exact: X% of total losing trades will be fakeouts (shuffled)."
    )
    
    loss_fakeout_chance = st.slider(
        "Losing Trade 'Fakeout' Chance (%)",
        min_value=0, max_value=100, value=25,
        help="Percentage of LOSING trades that hit TP 1 before reversing to SL."
    )

st.sidebar.subheader("Leverage & Fees")
leverage = st.sidebar.number_input("Leverage (x)", value=50, step=1)
maker_fee = st.sidebar.number_input("Maker Fee (%)", value=0.02, step=0.01, format="%.3f")
taker_fee = st.sidebar.number_input("Taker Fee (%)", value=0.05, step=0.01, format="%.3f")

st.sidebar.subheader("Order Types")
entry_type = st.sidebar.selectbox("Entry Type", ["Limit (Maker)", "Market (Taker)"], index=1)
tp_type = st.sidebar.selectbox("Take Profit Type", ["Limit (Maker)", "Market (Taker)"], index=0)
sl_type = st.sidebar.selectbox("Stop Loss Type", ["Limit (Maker)", "Market (Taker)"], index=1)

# --- MAIN EXECUTION ---
if run_button:
    # Remove the standard "Simulation Results" header to save space, 
    # we can use the first section header instead.
    
    # Pack TP targets into a list
    tp_targets = [(tp1_p, tp1_q), (tp2_p, tp2_q), (tp3_p, tp3_q)]

    summary, df = simulate_trading_detailed(
        start_bal, risk_percent, win_rate, sl_perc, n_trades, # Added risk_percent here
        leverage, maker_fee, taker_fee, entry_type, tp_type, sl_type,
        compound_rate, 
        win_rate_logic,
        tp_targets,
        loss_fakeout_chance,
        fakeout_logic
    )

    if summary:
        # Create a container for the top stats to keep them tight
        with st.container():
            st.markdown("### 📊 Outcome")
            # Combined Key Metrics & Counts to save vertical space
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Final Balance", f"${summary['final_balance']:,.2f}", delta=f"{summary['total_net_pnl']:,.2f}")
            c2.metric("Total Return", f"{summary['total_return_percent']:.2f}%")
            c3.metric("Trades Executed", f"{summary['num_trades_executed']}")
            c4.metric("Actual Win Rate", f"{summary['win_rate_actual_percent']:.1f}%")

            # Row 2: Money Flow & Trade Counts
            st.markdown("### 💰 Money Flow & Trade Breakdown")
            r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
            r2c1.metric("Total Won", f"${summary['total_gross_profit']:,.0f}")
            r2c2.metric("Total Lost", f"${summary['total_gross_loss']:,.0f}")
            r2c3.metric("Fees Paid", f"${summary['total_fees_paid']:,.0f}")
            r2c4.metric("Winning Trades", f"{summary['wins']}")
            
            # Losing Trades Metric with Custom Fakeout Text
            with r2c5:
                st.metric("Losing Trades", f"{summary['losses']}")
                # Display Actual Fakeout %
                if summary['losses'] > 0:
                    st.caption(f"Fakeouts: {summary['actual_fakeout_pct']:.1f}% ({summary['fakeout_losses']} trades)")
                else:
                    st.caption("No losses")

        st.markdown("---") # One single divider before the charts

        # Balance History Chart
        st.markdown("##### Balance History")
        st.pyplot(plot_balance_history(summary['balance_history'], start_bal))
        
        # Trade Log - Always Visible
        st.markdown("##### Trade Log")
        st.dataframe(df, use_container_width=True, height=600)

    else:
        st.error("Simulation failed.")
else:
    st.info("Click '🚀 Run Simulation' to start.")
