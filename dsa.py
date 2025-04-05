# app.py
import pandas as pd
from dash import Dash, html, dcc, Input, Output, State, no_update, ctx
import plotly.express as px
import plotly.graph_objects as go
import os
import re # Import regex

# --- Configuration & Data Loading ---
CSV_FILE = "Amazon Sale Report.csv"
DATE_FORMAT = "%m-%d-%y"

# Check if file exists
if not os.path.exists(CSV_FILE):
    print(f"Error: File not found at {CSV_FILE}")
    # Define columns, including optional ones like 'Order ID'
    df_cols = ["Date", "Category", "ship-state", "Status", "Amount", "ship-city", "Month", "Order ID"]
    df = pd.DataFrame(columns=df_cols)
else:
    try:
        # Load data
        df = pd.read_csv(CSV_FILE, low_memory=False)

        # --- Data Cleaning and Preprocessing ---
        # Convert 'Date' with specific format, coerce errors
        df["Date"] = pd.to_datetime(df["Date"], format=DATE_FORMAT, errors="coerce")
        df.dropna(subset=["Date"], inplace=True) # Drop rows where Date conversion failed

        # Create Month column (ensure it's string for consistent grouping/filtering)
        df["Month"] = df["Date"].dt.to_period("M").astype(str)

        # Handle potential numeric issues in Amount
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df.dropna(subset=["Amount"], inplace=True) # Drop rows where Amount is not a valid number

        # --- Ensure necessary columns exist and apply cleaning ---
        expected_cols = ['ship-state', 'Category', 'Status', 'ship-city', 'Order ID'] # Check for these
        for col in expected_cols:
            if col not in df.columns:
                print(f"Warning: Column '{col}' not found. Assigning default value ('Unknown' or None).")
                # Handle Order ID potentially missing differently if needed, but 'Unknown' string is safe
                df[col] = 'Unknown'
            else:
                # Apply cleaning based on column type
                if col in ['ship-state', 'ship-city']:
                    # Ensure string, strip whitespace, convert to title case
                    df[col] = df[col].astype(str).str.strip().str.title()
                elif col in ['Category', 'Status']:
                     # Ensure string, strip whitespace
                     df[col] = df[col].astype(str).str.strip()
                elif col == 'Order ID':
                    # Ensure string, strip whitespace
                    df[col] = df[col].astype(str).str.strip()

    except Exception as e:
        print(f"Error loading or processing data: {e}")
        # Create a dummy DataFrame if loading fails
        df_cols = ["Date", "Category", "ship-state", "Status", "Amount", "ship-city", "Month", "Order ID"]
        df = pd.DataFrame(columns=df_cols)


# --- Helper Functions ---
def create_empty_figure(title="No data available for selection"):
    """Creates an empty Plotly figure with a title."""
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": "🤷‍♀️ <br>No data to display.",
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {
                    "size": 16,
                    "color": "#888888"
                }
            }
        ],
        plot_bgcolor="#ffffff", # Match background
        paper_bgcolor="#ffffff"
    )
    return fig

# --- App Initialization ---
# Dash automatically picks up CSS from the 'assets' folder
app = Dash(__name__)
app.title = "Amazon Sales Dashboard"
server = app.server # For deployment


# --- App Layout ---
app.layout = html.Div([
    # Header Section
    html.Div([
        html.H1("📦 Amazon Sales Dashboard"),
        html.P("Explore your Amazon sales insights in a beautiful, interactive way.")
    ], className="header-container"),

    # Filters Section
    html.Div([
        html.Div([
            html.Label("📂 Category"),
            dcc.Dropdown(
                options=[{"label": c, "value": c} for c in sorted(df["Category"].dropna().unique())],
                multi=True,
                id="category-filter",
                placeholder="Select Categories..."
            )
        ], className="filter-item"),

        html.Div([
            html.Label("📍 State"),
            dcc.Dropdown(
                options=[{"label": s, "value": s} for s in sorted(df["ship-state"].dropna().unique())],
                multi=True,
                id="state-filter",
                placeholder="Select States..."
            )
        ], className="filter-item"),

        html.Div([
            html.Label("🚚 Order Status"),
            dcc.Dropdown(
                options=[{"label": s, "value": s} for s in df["Status"].dropna().unique()],
                multi=True,
                id="status-filter",
                placeholder="Select Statuses..."
            )
        ], className="filter-item")
    ], className="filter-container"),

    # KPIs Section
    html.Div(id="kpi-container", className="kpi-container"),

    html.Hr(), # Visual separator

    # Graphs Section - Structured in two rows
    html.Div([ # Outer container for all graphs
        # --- Row 1 ---
        html.Div([
            html.Div(dcc.Graph(id="sales-trend"), className="graph-item"), # Sales Trend
            html.Div(dcc.Graph(id="top-categories"), className="graph-item"), # Top Categories
        ], className="graph-row"), # Apply row class for styling

        # --- Row 2 ---
        html.Div([
            html.Div(dcc.Graph(id="top-cities"), className="graph-item"), # Top Cities
            html.Div(dcc.Graph(id="order-status"), className="graph-item"), # Order Status Pie Chart
        ], className="graph-row"), # Apply row class for styling

    ], className="all-graphs-container"), # Class for overall graph area padding/margins

    html.Hr(), # Visual separator

    # --- Enhanced Chatbot Section ---
    html.Div([
        html.H3("💬 Ask the Sales Data"), # Updated title
        html.Div([ # Wrapper Div for positioning input and button
            dcc.Textarea(
                id="user-input",
                placeholder="Ask about the current view: e.g., 'total sales', 'sales in Mumbai', 'details for order 123-456'...",
                style={'width': '100%'} # Let CSS handle most styling
            ),
            html.Button("Ask 🔎", id="send-btn", n_clicks=0), # Updated button text/icon
        ], className="input-wrapper"), # Apply the new CSS class for positioning
        html.Div(id="chat-response", children="🤖 Ask me to analyze the data based on your current filters.") # Default text
    ], className="chatbot-container") # Existing class for overall chatbot styling

])


# --- Callbacks ---

# Callback: Update Dashboard based on Filters
@app.callback(
    Output("sales-trend", "figure"),
    Output("top-categories", "figure"),
    Output("top-cities", "figure"),
    Output("order-status", "figure"),
    Output("kpi-container", "children"),
    Input("category-filter", "value"),
    Input("state-filter", "value"),
    Input("status-filter", "value")
)
def update_dashboard(selected_categories, selected_states, selected_statuses):
    # Start with the full dataframe
    dff = df.copy()

    # Apply filters if they are selected
    if selected_categories: dff = dff[dff["Category"].isin(selected_categories)]
    if selected_states: dff = dff[dff["ship-state"].isin(selected_states)]
    if selected_statuses: dff = dff[dff["Status"].isin(selected_statuses)]

    # Handle case where the filtered dataframe is empty
    if dff.empty:
        no_data_title = "No data for current filters"
        empty_fig = create_empty_figure(no_data_title)
        empty_kpis = [
            html.Div([html.H3("💰 Total Sales"), html.P("₹0.00")], className="kpi-card kpi-sales"),
            html.Div([html.H3("📦 Total Orders"), html.P("0")], className="kpi-card kpi-orders"),
            html.Div([html.H3("🧾 Avg Order Value"), html.P("₹0.00")], className="kpi-card kpi-avg-value")
        ]
        return empty_fig, empty_fig, empty_fig, empty_fig, empty_kpis

    # --- Calculate KPIs ---
    total_sales = dff["Amount"].sum()
    total_orders = len(dff) # Count rows for orders
    avg_order_value = total_sales / total_orders if total_orders > 0 else 0

    kpis = [
        html.Div([html.H3("💰 Total Sales"), html.P(f"₹{total_sales:,.2f}")], className="kpi-card kpi-sales"),
        html.Div([html.H3("📦 Total Orders"), html.P(f"{total_orders:,}")], className="kpi-card kpi-orders"),
        html.Div([html.H3("🧾 Avg Order Value"), html.P(f"₹{avg_order_value:,.2f}")], className="kpi-card kpi-avg-value")
    ]

    # --- Generate Graphs ---
    fig1 = create_empty_figure("📈 Monthly Sales Trend")
    fig2 = create_empty_figure("📊 Top 10 Categories by Sales")
    fig3 = create_empty_figure("📍 Top 10 Cities by Sales")
    fig4 = create_empty_figure("📋 Order Status Distribution")

    if not dff.empty: # Only generate graphs if data exists
        # 1. Monthly Sales Trend (Line Chart)
        if 'Month' in dff.columns and not dff['Month'].isnull().all():
            sales_trend = dff.groupby("Month")["Amount"].sum().reset_index().sort_values("Month")
            if not sales_trend.empty:
                fig1 = px.line(sales_trend, x="Month", y="Amount", markers=True, title="📈 Monthly Sales Trend", template="plotly_white")
                fig1.update_layout(title_x=0.5, margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                fig1.update_traces(line=dict(color='#667eea', width=2))

        # 2. Top 10 Categories by Sales (Bar Chart)
        if 'Category' in dff.columns and not dff['Category'].dropna().empty:
            top_cat = dff.groupby("Category")["Amount"].sum().nlargest(10).sort_values()
            if not top_cat.empty:
                fig2 = px.bar(x=top_cat.values, y=top_cat.index, orientation='h', title="📊 Top 10 Categories by Sales", template="plotly_white", labels={'x': 'Total Sales (₹)', 'y': 'Category'})
                fig2.update_layout(title_x=0.5, yaxis={'categoryorder':'total ascending'}, margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                fig2.update_traces(marker_color='#764ba2')

        # 3. Top 10 Cities by Sales (Bar Chart)
        if 'ship-city' in dff.columns and not dff['ship-city'].dropna().empty:
            top_city = dff.groupby("ship-city")["Amount"].sum().nlargest(10).sort_values()
            if not top_city.empty:
                fig3 = px.bar(x=top_city.values, y=top_city.index, orientation='h', title="📍 Top 10 Cities by Sales", template="plotly_white", labels={'x': 'Total Sales (₹)', 'y': 'City'})
                fig3.update_layout(title_x=0.5, yaxis={'categoryorder':'total ascending'}, margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                fig3.update_traces(marker_color='#48bb78')

        # 4. Order Status Distribution (Pie Chart)
        if 'Status' in dff.columns and not dff['Status'].dropna().empty:
            order_status = dff["Status"].value_counts()
            if not order_status.empty:
                fig4 = px.pie(names=order_status.index, values=order_status.values, title="📋 Order Status Distribution", template="plotly_white", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig4.update_layout(title_x=0.5, margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                fig4.update_traces(textinfo='percent+label', textposition='inside', insidetextorientation='radial', marker=dict(line=dict(color='#ffffff', width=1.5)))

    return fig1, fig2, fig3, fig4, kpis


# Callback: Enhanced Chatbot Analyzing Filtered Data
@app.callback(
    Output("chat-response", "children"),
    Input("send-btn", "n_clicks"),
    State("user-input", "value"),
    State("category-filter", "value"),
    State("state-filter", "value"),
    State("status-filter", "value"),
    prevent_initial_call=True
)
def analyze_data_view(n_clicks, user_message, selected_categories, selected_states, selected_statuses):
    bot_prefix = "🤖 " # Define prefix here

    if not user_message:
        return dcc.Markdown(bot_prefix + "Please ask a question about the current data view.")

    # --- Recreate the filtered dataframe (dff) based on current filter states ---
    dff = df.copy()
    filter_active = False
    filter_desc = "overall data" # Description of the data scope

    if selected_categories or selected_states or selected_statuses:
        filter_desc = "current filtered view" # Update scope description
        filter_active = True
        if selected_categories: dff = dff[dff["Category"].isin(selected_categories)]
        if selected_states: dff = dff[dff["ship-state"].isin(selected_states)]
        if selected_statuses: dff = dff[dff["Status"].isin(selected_statuses)]

    # --- Handle empty filtered data ---
    if dff.empty:
        return dcc.Markdown(bot_prefix + f"📉 No data found for the {filter_desc}. Please broaden your filters.")

    # --- Analyze the request (using regex and specific filtering on dff) ---
    msg = user_message.lower().strip()
    response = f"🤔 I'm not sure how to interpret that for the {filter_desc}. Try asking about totals, averages, tops, counts, or specifics like 'sales in Mumbai' or 'details for order 123-456'." # Default response

    try:
        # Check for specific entity queries first
        match_specific = re.search(r"(sales|orders|count)\s+(?:in|for|from)\s+([\w\s.-]+)", msg)
        match_order = re.search(r"(details|info|status)\s+(?:for|of)\s+order\s+([\w\-/]+)", msg)

        if match_specific:
            metric = match_specific.group(1); entity = match_specific.group(2).strip(); entity_title = entity.title()
            found_entity = False
            # Check City
            if 'ship-city' in dff.columns and entity_title in dff['ship-city'].unique():
                specific_df = dff[dff['ship-city'] == entity_title]; metric_val = specific_df['Amount'].sum() if metric == "sales" else len(specific_df)
                response = f"🏙️ {metric.title()} for city **{entity_title}** in the {filter_desc}: **{'₹' if metric == 'sales' else ''}{metric_val:,.2f if metric == 'sales' else ','}**."
                found_entity = True
            # Check State
            elif 'ship-state' in dff.columns and entity_title in dff['ship-state'].unique():
                 specific_df = dff[dff['ship-state'] == entity_title]; metric_val = specific_df['Amount'].sum() if metric == "sales" else len(specific_df)
                 response = f"📍 {metric.title()} for state **{entity_title}** in the {filter_desc}: **{'₹' if metric == 'sales' else ''}{metric_val:,.2f if metric == 'sales' else ','}**."
                 found_entity = True
             # Check Category (case-insensitive)
            elif 'Category' in dff.columns and dff['Category'].str.contains(entity, case=False, na=False).any():
                 specific_df = dff[dff['Category'].str.contains(entity, case=False, na=False)]; matched_cats = specific_df['Category'].unique(); cat_name_display = matched_cats[0] if len(matched_cats) == 1 else f"categories matching '{entity}'"
                 metric_val = specific_df['Amount'].sum() if metric == "sales" else len(specific_df)
                 response = f"📂 {metric.title()} for **{cat_name_display}** in the {filter_desc}: **{'₹' if metric == 'sales' else ''}{metric_val:,.2f if metric == 'sales' else ','}**."
                 found_entity = True
            if not found_entity: response = f"❓ Could not find '{entity}' as a city, state, or category in the {filter_desc}."

        elif match_order:
            action = match_order.group(1); order_id = match_order.group(2).strip()
            if 'Order ID' not in dff.columns: response = "❗ Cannot look up orders as 'Order ID' column is missing."
            else:
                order_df = dff[dff['Order ID'] == order_id] # Exact match
                if not order_df.empty:
                    order_data = order_df.iloc[0]
                    if action == "status": response = f"🏷️ Status for order **{order_id}** in {filter_desc}: **{order_data.get('Status', 'N/A')}**."
                    else: # details or info
                        details = [f"📋 Details for Order ID **{order_id}** (found in {filter_desc}):",
                                   f"- **Date:** {pd.to_datetime(order_data.get('Date', '')).strftime('%Y-%m-%d') if pd.notna(order_data.get('Date', '')) else 'N/A'}",
                                   f"- **Status:** {order_data.get('Status', 'N/A')}",
                                   f"- **Amount:** ₹{order_data.get('Amount', 0):,.2f}",
                                   f"- **Category:** {order_data.get('Category', 'N/A')}",
                                   f"- **Ship to City:** {order_data.get('ship-city', 'N/A')}",
                                   f"- **Ship to State:** {order_data.get('ship-state', 'N/A')}"]
                        response = "\n".join(details)
                else:
                    original_order_df = df[df['Order ID'] == order_id] # Check original data
                    if not original_order_df.empty: response = f"🚫 Order **{order_id}** exists but is not in the {filter_desc}. Try removing filters."
                    else: response = f"🚫 Order ID **{order_id}** not found in the dataset."

        # --- Fallback to General Aggregate Queries ---
        elif "total sales" in msg or "total revenue" in msg:
            total_sales = dff['Amount'].sum(); response = f"📊 Total sales for the {filter_desc}: **₹{total_sales:,.2f}**."
        elif "how many orders" in msg or "total orders" in msg or "order count" in msg:
             total_orders = len(dff); response = f"🔢 Orders in the {filter_desc}: **{total_orders:,}**."
        elif "average amount" in msg or "average sales" in msg:
            if len(dff) > 0: avg_value = dff["Amount"].mean(); response = f"⚖️ Average order amount for the {filter_desc}: **₹{avg_value:,.2f}**."
            else: response = f"📉 Cannot calculate average for the {filter_desc}."
        elif "top category" in msg:
            if 'Category' in dff.columns and not dff['Category'].dropna().empty: top_cat_calc = dff.groupby("Category")["Amount"].sum().idxmax(); top_cat_sales = dff.groupby("Category")["Amount"].sum().max(); response = f"🏆 Top category (by sales) in {filter_desc}: **{top_cat_calc}** (₹{top_cat_sales:,.2f})."
            else: response = f"❓ Cannot determine top category for {filter_desc}."
        elif "top city" in msg:
            if 'ship-city' in dff.columns and not dff['ship-city'].dropna().empty and dff['ship-city'].nunique() > 0: top_city_calc = dff.groupby("ship-city")["Amount"].sum().idxmax(); top_city_sales = dff.groupby("ship-city")["Amount"].sum().max(); response = f"🏙️ Top city (by sales) in {filter_desc}: **{top_city_calc}** (₹{top_city_sales:,.2f})."
            else: response = f"❓ Cannot determine top city for {filter_desc}."
        elif "top state" in msg:
             if 'ship-state' in dff.columns and not dff['ship-state'].dropna().empty and dff['ship-state'].nunique() > 0: top_state_calc = dff.groupby("ship-state")["Amount"].sum().idxmax(); top_state_sales = dff.groupby("ship-state")["Amount"].sum().max(); response = f"📍 Top state (by sales) in {filter_desc}: **{top_state_calc}** (₹{top_state_sales:,.2f})."
             else: response = f"❓ Cannot determine top state for {filter_desc}."
        elif "status summary" in msg or "order status" in msg:
             if 'Status' in dff.columns and not dff['Status'].dropna().empty:
                 status_counts = dff['Status'].value_counts(); response_list = [f"📋 Status summary for {filter_desc}:"]
                 for status, count in status_counts.items(): response_list.append(f"- **{status}:** {count:,} orders")
                 response = "\n".join(response_list)
             else: response = f"❓ No status info for {filter_desc}."
        elif "count" in msg and ("orders" in msg or "status" in msg): # General count status
             match_status_count = re.search(r"count ([\w\s]+?)\s*(?:orders|status)", msg)
             if match_status_count and 'Status' in dff.columns:
                 status_query = match_status_count.group(1).strip()
                 # Use contains for flexibility
                 count = dff[dff['Status'].str.contains(status_query, case=False, na=False)].shape[0]
                 response = f"🔢 Found **{count:,}** orders with status containing '{status_query}' in {filter_desc}."
        elif "hello" in msg or "hi" in msg: response = f"👋 Hello! I can analyze the {filter_desc}. What would you like to know?"
        elif "bye" in msg or "thanks" in msg: response = "👍 Happy to help analyze!"

    except Exception as e:
        print(f"Analysis Error: {e}")
        response = f"🤖 Oops! Something went wrong while analyzing the {filter_desc}. Please check the data or try a different question."

    # Add bot prefix before returning
    return dcc.Markdown(bot_prefix + response)


# --- Run App ---
if __name__ == "__main__":
    app.run(debug=True) # Set debug=False for production