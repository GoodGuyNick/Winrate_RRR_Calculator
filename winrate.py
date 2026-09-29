import streamlit as st
import pandas as pd
import random
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# --- STREAMLIT UI SETUP & CSS ---
st.set_page_config(layout="wide", page_title="Trading Simulator")

# Inject AGGRESSIVE CSS to reduce whitespace everywhere and scale down metrics
st.markdown("""
    <style>
        /* --- SIDEBAR TWEAKS --- */
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
        .main .block-container {
            padding-top: 1.2rem !important; 
        }
        
        .main [data-testid="stVerticalBlock"] > div {
            gap: 0.3rem !important;
        }
        
        /* Reduce header margins in main area */
        .main h3 {
            padding-top: 0.1rem !important;
            padding-bottom: 0.1rem !important;
            margin-top: 0rem !important;
            margin-bottom: 0.2rem !important;
            font-size: 1.1rem !important;
        }
        
        .main h5 {
            padding-top: 0.2rem !important;
            padding-bottom: 0.1rem !important;
            margin-top: 0.2rem !important;
            margin-bottom: 0.1rem !important;
            font-size: 0.95rem !important;
        }
        
        .main hr {
            margin-top: 0.3rem !important;
            margin-bottom: 0.3rem !important;
        }

        /* --- METRIC SCALING & FONT COMPACTNESS --- */
        [data-testid="stMetricLabel"] {
            font-size: 0.75rem !important;
            font-weight: 500 !important;
            margin-bottom: -4px !important;
            white-space: nowrap !important;
        }
        
        [data-testid="stMetricValue"] {
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            line-height: 1.15 !important;
        }

        [data-testid="stMetricDelta"] {
            font-size: 0.7rem !important;
        }

        [data-testid="stMetric"] {
            padding: 4px 8px !important;
            background-color: rgba(255, 255, 255, 0.03);
            border-radius: 5px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        div[data-testid="stCaptionContainer"] {
            font-size: 0.7rem !important;
            margin-top: -2px !important;
            line-height: 1.0 !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Leveraged Trading Strategy Simulator")

# --- Strategy Parameter Analysis & Kelly Helper ---
def analyze_strategy_parameters(
    win_rate_percent,
    stop_loss_percent,
    tp_targets,
    maker_fee_percent,
    taker_fee_percent,
    entry_order_type,
    tp_order_type,
    sl_order_type,
    loss_fakeout_chance_percent,
    leverage
):
    W = win_rate_percent / 100.0
    SL = stop_loss_percent / 100.0
    F = loss_fakeout_chance_percent / 100.0
    
    m_fee = maker_fee_percent / 100.0
    t_fee = taker_fee_percent / 100.0
    
    entry_fee_rate = m_fee if entry_order_type == "Limit (Maker)" else t_fee
    tp_exit_fee_rate = m_fee if tp_order_type == "Limit (Maker)" else t_fee
    sl_exit_fee_rate = m_fee if sl_order_type == "Limit (Maker)" else t_fee
    
    # Normalize TP targets
    tp1_target, tp1_qty = tp_targets[0]
    tp2_target, tp2_qty = tp_targets[1]
    tp3_target, tp3_qty = tp_targets[2]

    q1, q2, q3 = tp1_qty / 100.0, tp2_qty / 100.0, tp3_qty / 100.0
    total_q = q1 + q2 + q3
    if total_q > 0:
        q1, q2, q3 = q1 / total_q, q2 / total_q, q3 / total_q
    
    p1, p2, p3 = tp1_target / 100.0, tp2_target / 100.0, tp3_target / 100.0
    
    # Net Win return per unit leverage
    g_win = q1 * p1 + q2 * p2 + q3 * p3
    b_net = g_win - entry_fee_rate - tp_exit_fee_rate * (1.0 + g_win)
    
    # Direct Loss return per unit leverage
    g_loss_direct = SL
    a_direct = g_loss_direct + entry_fee_rate + sl_exit_fee_rate * max(0.0, 1.0 - SL)
    
    # Fakeout Loss return per unit leverage
    g_fake_pnl = q1 * p1 - (1.0 - q1) * SL
    fake_exit_fee = (q1 * (1.0 + p1) * tp_exit_fee_rate) + (max(0.0, (1.0 - q1) * (1.0 - SL)) * sl_exit_fee_rate)
    net_fake_pnl = g_fake_pnl - entry_fee_rate - fake_exit_fee
    a_fake = -net_fake_pnl
    
    # Weighted Average Loss per unit leverage
    a_net = (1.0 - F) * a_direct + F * a_fake
    
    # Parameter RRR (Net Win / Net Loss)
    param_rrr = (b_net / a_net) if a_net > 0 else None
    
    # Expected Value check
    ev = W * b_net - (1.0 - W) * a_net
    
    if ev <= 0 or b_net <= 0 or a_net <= 0:
        opt_full, opt_half = None, None
    else:
        kelly_full = (W * b_net - (1.0 - W) * a_net) / (a_net * b_net)
        max_safe_lev = 0.95 / a_net
        opt_full = min(kelly_full, max_safe_lev)
        opt_half = opt_full / 2.0
    
    # Return on margin %
    net_reward_on_margin = b_net * leverage * 100.0
    net_risk_on_margin = a_net * leverage * 100.0
    
    # Expected Value per trade on Margin basis (%)
    ev_per_trade_percent = (W * net_reward_on_margin) - ((1.0 - W) * net_risk_on_margin)

    return {
        "opt_full": opt_full,
        "opt_half": opt_half,
        "param_rrr": param_rrr,
        "net_reward_on_margin": net_reward_on_margin,
        "net_risk_on_margin": net_risk_on_margin,
        "ev_per_trade_percent": ev_per_trade_percent
    }

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
    fakeout_logic,
    enable_skim=False,
    harvest_threshold_percent=100.0,
    skim_percent_of_main_bank=50.0
):
    current_balance = starting_balance
    current_baseline = starting_balance
    balance_history = [starting_balance]
    trade_details = []
    
    # Init trackers
    results = {
        "wins": 0, 
        "losses": 0,
        "fakeout_losses": 0,
        "total_fees_paid": 0.0,
        "total_gross_profit": 0.0,
        "total_gross_loss": 0.0,
        "total_skimmed": 0.0,
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

    # --- Parameter Sizing & Optimal Leverage Analysis ---
    strat_analysis = analyze_strategy_parameters(
        win_rate_percent, stop_loss_percent, tp_targets,
        maker_fee_percent, taker_fee_percent, entry_order_type,
        tp_order_type, sl_order_type, loss_fakeout_chance_percent, leverage
    )

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
        if win_rate_logic == "🎯 Exact Count (Fixed)":
            expected_losses = num_trades - int(round(num_trades * win_rate))
        else:
            expected_losses = int(num_trades * (1 - win_rate))
        
        num_fakeouts = int(round(expected_losses * loss_fakeout_prob))
        if expected_losses > 0:
            fakeout_loss_indices = random.sample(range(expected_losses), min(num_fakeouts, expected_losses))
            pre_determined_fakeouts = set(fakeout_loss_indices)
    
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

        # --- Calculate PnL ---
        gross_pnl = 0.0
        exit_fees = 0.0
        outcome_str = ""

        tp1_target, tp1_qty = tp_targets[0]
        tp2_target, tp2_qty = tp_targets[1]
        tp3_target, tp3_qty = tp_targets[2]

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
            
            chunk_margin_1 = position_size_basis * q1
            chunk_pnl_1 = chunk_margin_1 * (tp1_target/100.0) * leverage
            chunk_exit_fee_1 = (chunk_margin_1 * leverage + chunk_pnl_1) * tp_exit_fee_rate
            
            chunk_margin_2 = position_size_basis * q2
            chunk_pnl_2 = chunk_margin_2 * (tp2_target/100.0) * leverage
            chunk_exit_fee_2 = (chunk_margin_2 * leverage + chunk_pnl_2) * tp_exit_fee_rate

            chunk_margin_3 = position_size_basis * q3
            chunk_pnl_3 = chunk_margin_3 * (tp3_target/100.0) * leverage
            chunk_exit_fee_3 = (chunk_margin_3 * leverage + chunk_pnl_3) * tp_exit_fee_rate

            gross_pnl = chunk_pnl_1 + chunk_pnl_2 + chunk_pnl_3
            exit_fees = chunk_exit_fee_1 + chunk_exit_fee_2 + chunk_exit_fee_3
            
            results["total_gross_profit"] += gross_pnl

        else:
            results["losses"] += 1
            
            is_fakeout = False
            if fakeout_logic == "🎯 Exact Count (Fixed)":
                is_fakeout = loss_counter in pre_determined_fakeouts
            else:
                is_fakeout = random.random() < loss_fakeout_prob
            
            loss_counter += 1

            if is_fakeout:
                results["fakeout_losses"] += 1
                outcome_str = "LOSS (Fakeout: TP1 -> SL)"
                
                chunk_margin_1 = position_size_basis * q1
                chunk_pnl_1 = chunk_margin_1 * (tp1_target/100.0) * leverage 
                chunk_exit_fee_1 = (chunk_margin_1 * leverage + chunk_pnl_1) * tp_exit_fee_rate
                
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

        # --- Skim Vault System ---
        skimmed_this_trade = 0.0
        if enable_skim and harvest_threshold_percent > 0 and skim_percent_of_main_bank > 0:
            target_balance = current_baseline * (1.0 + harvest_threshold_percent / 100.0)
            if current_balance >= target_balance:
                skim_amount = current_baseline * (skim_percent_of_main_bank / 100.0)
                if skim_amount > 0:
                    skimmed_this_trade = min(skim_amount, current_balance)
                    current_balance -= skimmed_this_trade
                    results["total_skimmed"] += skimmed_this_trade
                    current_baseline = current_balance

        balance_history.append(current_balance)
        
        # Return on margin %
        return_on_margin_pct = (net_pnl / position_size_basis) * 100.0
        
        trade_details.append({
            "Trade #": i,
            "Balance Before": round(balance_before_trade, 2),
            "Margin Used": round(position_size_basis, 2),
            "Outcome": outcome_str,
            "Gross P/L ($)": round(gross_pnl, 2),
            "Total Fee ($)": round(total_fee, 4),
            "Net P/L ($)": round(net_pnl, 2),
            "Return on Margin (%)": round(return_on_margin_pct, 2),
            "Skimmed": round(skimmed_this_trade, 2),
            "Balance After": round(current_balance, 2)
        })

    # --- Summary ---
    final_balance = balance_history[-1]
    total_net_pnl = final_balance - starting_balance
    total_return_percent = (total_net_pnl / starting_balance) * 100 if starting_balance > 0 else 0
    num_trades_executed = len(trade_details)
    
    actual_fakeout_pct = 0
    if results["losses"] > 0:
        actual_fakeout_pct = (results["fakeout_losses"] / results["losses"]) * 100

    actual_ev_dollars = (total_net_pnl / num_trades_executed) if num_trades_executed > 0 else 0.0
    actual_ev_percent = (sum(t["Return on Margin (%)"] for t in trade_details) / num_trades_executed) if num_trades_executed > 0 else 0.0

    summary = {
        "starting_balance": starting_balance,
        "final_balance": round(final_balance, 2),
        "total_net_pnl": round(total_net_pnl, 2),
        "total_return_percent": round(total_return_percent, 2),
        "num_trades_executed": num_trades_executed,
        "wins": results["wins"],
        "losses": results["losses"],
        "fakeout_losses": results["fakeout_losses"],
        "actual_fakeout_pct": actual_fakeout_pct,
        "win_rate_actual_percent": (results["wins"] / num_trades_executed * 100) if num_trades_executed > 0 else 0,
        "total_fees_paid": round(results["total_fees_paid"], 2),
        "total_gross_profit": round(results["total_gross_profit"], 2),
        "total_gross_loss": round(results["total_gross_loss"], 2),
        "total_skimmed": round(results["total_skimmed"], 2),
        "param_rrr": strat_analysis["param_rrr"],
        "net_reward_on_margin": strat_analysis["net_reward_on_margin"],
        "net_risk_on_margin": strat_analysis["net_risk_on_margin"],
        "ev_per_trade_percent": strat_analysis["ev_per_trade_percent"],
        "actual_ev_dollars": round(actual_ev_dollars, 2),
        "actual_ev_percent": round(actual_ev_percent, 2),
        "balance_history": balance_history,
        "opt_leverage_full": strat_analysis["opt_full"],
        "opt_leverage_half": strat_analysis["opt_half"]
    }

    return summary, pd.DataFrame(trade_details)


# --- Plotting Function ---
def plot_balance_history(balance_history, starting_balance, title="Trading Simulation Balance"):
    if not balance_history:
        return None
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(range(len(balance_history)), balance_history, marker='.', linestyle='-', markersize=4, label='Balance')
    ax.axhline(y=starting_balance, color='r', linestyle='--', label=f'Start (${starting_balance:,.2f})')
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Trade Number", fontsize=8)
    ax.set_ylabel("Balance (USD)", fontsize=8)
    ax.tick_params(axis='both', which='major', labelsize=8)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(fontsize=8)
    formatter = mticker.StrMethodFormatter('${x:,.2f}')
    ax.yaxis.set_major_formatter(formatter)
    plt.tight_layout()
    return fig


# --- SIDEBAR ---
st.sidebar.subheader("Run Control") 
run_button = st.sidebar.button("🚀 Run Simulation", type="primary")

st.sidebar.subheader("Simulation Parameters")

compound_rate = st.sidebar.slider(
    label="Compounding Rate (%)",
    min_value=0,
    max_value=100,
    value=100,
    step=10,
    format="%d%%",
    help="0% = Fixed Trade Size. 100% = Full Compounding."
)

col_sb, col_lev = st.sidebar.columns(2)
with col_sb:
    start_bal = st.number_input("Starting Balance", value=10.0, step=10.0)
with col_lev:
    leverage = st.number_input("Leverage (x)", value=500, step=1)

# --- Skim Vault System ---
with st.sidebar.expander("🏦 Skim Vault System", expanded=False):
    enable_skim = st.checkbox("Enable Skim Vault", value=False)
    col_ht, col_sa = st.columns(2)
    with col_ht:
        harvest_threshold = st.number_input(
            "Harvest Threshold (%)", 
            value=100.0, 
            step=10.0, 
            help="Wallet return % required to trigger skim (e.g. 100% = doubling account)."
        )
    with col_sa:
        skim_percent = st.number_input(
            "Skim Amount (% of Main Bank)", 
            value=50.0, 
            step=10.0, 
            help="Percentage of main bank (starting balance) to skim back into Cold Bank."
        )

risk_percent = st.sidebar.number_input(
    "Margin / Risk per Trade (%)", 
    value=100.0, 
    step=10.0, 
    min_value=1.0, 
    max_value=100.0, 
    help="Percentage of your available balance to allocate as margin for each trade."
)
col_wr, col_nt = st.sidebar.columns(2)
with col_wr:
    win_rate = st.number_input("Win Rate (%)", value=60.0, step=1.0)
with col_nt:
    n_trades = st.number_input("Number of Trades", value=60, step=1)

win_rate_logic = st.sidebar.radio(
    "Win Rate Logic",
    options=["🎲 Probabilistic (Pure Luck)", "🎯 Exact Count (Fixed)"],
    index=1,
    help="Probabilistic: 60% WR = 60% chance per trade. Exact: 60% WR = Exactly 60 wins out of 100 trades (shuffled)."
)

# --- Advanced Exit Settings ---
with st.sidebar.expander("🎯 Exit Settings (TP Levels & SL)", expanded=False):
    st.write("**Partial Take Profit Levels**")
    c1, c2 = st.columns(2)
    with c1:
        tp1_p = st.number_input("TP 1: Price %", value=0.0, step=0.005, format="%.3f")
        tp2_p = st.number_input("TP 2 Main: Price %", value=0.060, step=0.005, format="%.3f")
        tp3_p = st.number_input("TP 3: Price %", value=0.0, step=0.005, format="%.3f")
    with c2:
        tp1_q = st.number_input("TP 1: Size %", value=0, step=5)
        tp2_q = st.number_input("TP 2 Main: Size %", value=100, step=5)
        tp3_q = st.number_input("TP 3: Size %", value=0, step=5)
    
    st.caption(f"Total Size to Close: {tp1_q + tp2_q + tp3_q}% (Should be 100%)")
    
    st.write("**Stop Loss Behavior**")
    sl_perc = st.number_input("Stop Loss Distance (%)", value=0.035, step=0.005, format="%.3f")
    
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

st.sidebar.subheader("Order Types & Fees")
col_mk, col_tk = st.sidebar.columns(2)
with col_mk:
    maker_fee = st.number_input("Maker Fee (%)", value=0.02, step=0.0001, format="%.5f")
with col_tk:
    taker_fee = st.number_input("Taker Fee (%)", value=0.00225, step=0.0001, format="%.5f")

entry_type = st.sidebar.selectbox("Entry Type", ["Limit (Maker)", "Market (Taker)"], index=1)
tp_type = st.sidebar.selectbox("Take Profit Type", ["Limit (Maker)", "Market (Taker)"], index=1)
sl_type = st.sidebar.selectbox("Stop Loss Type", ["Limit (Maker)", "Market (Taker)"], index=1)

# --- MAIN EXECUTION ---
if run_button:
    tp_targets = [(tp1_p, tp1_q), (tp2_p, tp2_q), (tp3_p, tp3_q)]

    summary, df = simulate_trading_detailed(
        start_bal, risk_percent, win_rate, sl_perc, n_trades,
        leverage, maker_fee, taker_fee, entry_type, tp_type, sl_type,
        compound_rate, 
        win_rate_logic,
        tp_targets,
        loss_fakeout_chance,
        fakeout_logic,
        enable_skim,
        harvest_threshold,
        skim_percent
    )

    if summary:
        with st.container():
            st.markdown("### 📊 Performance & Breakdown")
            
            # Row 1: Key Performance Metrics
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Final Balance", f"${summary['final_balance']:,.2f}", delta=f"{summary['total_net_pnl']:,.2f}")
                st.caption(f"Total skimmed: {summary['total_skimmed']:,.2f}")
            c2.metric("Total Return", f"{summary['total_return_percent']:.2f}%")
            c3.metric("Trades Executed", f"{summary['num_trades_executed']}")
            c4.metric("Actual Win Rate", f"{summary['win_rate_actual_percent']:.1f}%")
            with c5:
                if summary['opt_leverage_full'] is not None:
                    st.metric(
                        "Recommended Leverage", 
                        f"{summary['opt_leverage_half']:.1f}x - {summary['opt_leverage_full']:.1f}x",
                        help="Calculated via the Kelly Criterion considering your Win Rate, TP/SL targets, fees, and fakeout chance."
                    )
                    st.caption(f"Half: {summary['opt_leverage_half']:.1f}x | Full: {summary['opt_leverage_full']:.1f}x")
                else:
                    st.metric("Rec. Leverage", "N/A")
                    st.caption("Negative Expected Value Strategy")

            # Row 2: Money Flow, RRR, EV, Fees & Counts
            r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
            
            r2c1.metric("Total Won / Lost", f"+{summary['total_gross_profit']:,.0f} / -{abs(summary['total_gross_loss']):,.0f}")
            
            with r2c2:
                if summary['param_rrr'] is not None:
                    st.metric(
                        "Actual RRR", 
                        f"1 : {summary['param_rrr']:.2f}",
                        help="Net Risk-to-Reward Ratio calculated strictly from TP/SL price targets, leverage, order fees, and fakeout chance."
                    )
                    st.caption(f"Net Win: +{summary['net_reward_on_margin']:.1f}% | Loss: -{summary['net_risk_on_margin']:.1f}%")
                else:
                    st.metric("Actual RRR", "N/A")
                    st.caption("Invalid parameter targets")

            with r2c3:
				# Use Probabilistic (Pure Luck) to see deviations in Actual EV and Theo EV.
                ev_pct_sign = "+" if summary['actual_ev_percent'] >= 0 else ""
                st.metric(
                    "Expected Value (EV)",
                    f"{ev_pct_sign}{summary['actual_ev_percent']:.2f}%",
                    help="Realized average Net Profit per trade relative to margin used (after fees and fakeout chance)."
                )
                theo_sign = "+" if summary['ev_per_trade_percent'] >= 0 else ""
                st.caption(f"Theo: {theo_sign}{summary['ev_per_trade_percent']:.2f}% | Avg: ${summary['actual_ev_dollars']:,.2f}")

            r2c4.metric("Fees Paid", f"${summary['total_fees_paid']:,.2f}")

            with r2c5:
                st.metric("Win / Loss Trades", f"{summary['wins']} / {summary['losses']}")
                if summary['losses'] > 0:
                    st.caption(f"Fakeouts: {summary['actual_fakeout_pct']:.1f}% ({summary['fakeout_losses']})")
                else:
                    st.caption("No losing trades")

        st.markdown("---")

        # Balance History Chart
        st.markdown("##### Balance History")
        st.pyplot(plot_balance_history(summary['balance_history'], start_bal))
        
        # Trade Log
        st.markdown("##### Trade Log")
        st.dataframe(df, use_container_width=True, height=500)

    else:
        st.error("Simulation failed.")
else:
    st.info("Click '🚀 Run Simulation' to start.")
