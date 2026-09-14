import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO

# 多伦多时区
TORONTO_TZ = ZoneInfo("America/Toronto")

# 页面配置
st.set_page_config(
    page_title="Cozy Crumb Cake 订单管理系统",
    page_icon="🧁",
    layout="wide"
)

# 自定义粉色主题样式
st.markdown("""
<style>
    .stApp {
        background-color: #f9f5f6;
    }
    h1, h2, h3 {
        color: #d85a84 !important;
    }
    .stButton>button {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

DB_NAME = "cupcake_sales.db"

FLAVORS = [
    "Vanilla", "Chocolate", "Strawberry", "Cookie Cream",
    "Salty Caremel", "Tiramisu", "Pistachio", "Macha", "Oreo"
]


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            flavors_detail TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total REAL NOT NULL,
            request_date TEXT NOT NULL,
            record_time TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def calculate_total(qty):
    bundles_12 = qty // 12
    remainder_12 = qty % 12
    bundles_6 = remainder_12 // 6
    remainder_6 = remainder_12 % 6
    total = (bundles_12 * 40.0) + (bundles_6 * 20.0) + (remainder_6 * 3.5)
    return total


def load_records():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT id, name, flavors_detail, quantity, total, request_date, record_time "
        "FROM sales ORDER BY id DESC",
        conn
    )
    conn.close()
    return df


def save_order(name, flavor_qtys, request_date, custom_total=None, edit_id=None):
    order_items = []
    total_qty = 0

    for flavor, qty in flavor_qtys.items():
        if qty and qty > 0:
            order_items.append(f"{flavor}: {qty}")
            total_qty += qty

    if total_qty == 0:
        return False, "请至少选择一个口味并输入数量！"

    flavors_detail_str = ", ".join(order_items)
    
    if custom_total is not None and custom_total > 0:
        total_price = custom_total
    else:
        total_price = calculate_total(total_qty)
    
    # 使用多伦多时间
    current_time = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if edit_id is None:
        cursor.execute(
            "INSERT INTO sales (name, flavors_detail, quantity, total, request_date, record_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name.strip(), flavors_detail_str, total_qty, total_price, request_date, current_time)
        )
        msg = f"订单记录成功！\n\n客户：{name}\n总数量：{total_qty} 个\n总计：${total_price:.2f}"
    else:
        cursor.execute(
            "UPDATE sales SET name=?, flavors_detail=?, quantity=?, total=?, request_date=? WHERE id=?",
            (name.strip(), flavors_detail_str, total_qty, total_price, request_date, edit_id)
        )
        msg = f"订单修改成功！\n\n订单 ID：{edit_id}\n客户：{name}\n总数量：{total_qty} 个\n总计：${total_price:.2f}"

    conn.commit()
    conn.close()
    return True, msg


def delete_all_records():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales")
    conn.commit()
    conn.close()


# ---------------- 弹窗定义 ----------------
@st.dialog("⚠️ 提示")
def show_warning(message):
    st.write(message)
    if st.button("知道了", use_container_width=True):
        st.rerun()


@st.dialog("✅ 提交成功")
def show_success(message):
    st.write(message)
    if st.button("确定", type="primary", use_container_width=True):
        st.session_state.edit_id = None
        st.session_state.edit_data = {}
        st.session_state.form_reset += 1
        st.rerun()


@st.dialog("⚠️ 确认清空")
def confirm_clear_dialog():
    st.write("确定要清空**所有历史销售记录**吗？")
    st.write("此操作不可恢复！")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认清空", type="primary", use_container_width=True):
            delete_all_records()
            st.session_state.confirm_clear = False
            st.success("已清空所有历史记录！")
            st.rerun()
    with col2:
        if st.button("取消", use_container_width=True):
            st.session_state.confirm_clear = False
            st.rerun()


# 初始化
init_db()

# 使用多伦多时间显示今天日期
today_str = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")

st.title("🧁 Cozy Crumb Cake 订单管理系统")
st.caption(f"📅 Today: {today_str} （多伦多时间）")

# 初始化 session_state
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False
if "form_reset" not in st.session_state:
    st.session_state.form_reset = 0

# ==================== 订单输入区域 ====================
st.subheader("📝 新建 / 修改订单")

col1, col2 = st.columns(2)
with col1:
    default_name = st.session_state.edit_data.get("name", "")
    name = st.text_input("Customer Name", value=default_name, placeholder="请输入客户姓名", key=f"name_{st.session_state.form_reset}")

with col2:
    # 默认使用多伦多今天的日期
    default_date = st.session_state.edit_data.get("request_date", today_str)
    request_date = st.text_input("Request Date", value=default_date, placeholder="例如：2026-09-13", key=f"date_{st.session_state.form_reset}")

st.markdown("**选择各口味数量**（$3.5/个，6个$20，12个$40）")

flavor_qtys = {}
cols = st.columns(3)
for i, flavor in enumerate(FLAVORS):
    with cols[i % 3]:
        default_qty = st.session_state.edit_data.get("flavors", {}).get(flavor, 0)
        qty = st.number_input(
            flavor,
            min_value=0,
            step=1,
            value=int(default_qty) if default_qty else 0,
            key=f"flavor_{flavor}_{st.session_state.form_reset}"
        )
        flavor_qtys[flavor] = qty

# 实时计算总金额
current_qty = sum(q for q in flavor_qtys.values() if q)
auto_total = calculate_total(current_qty)

st.markdown("---")
st.markdown(f"### 💵 总金额： **${auto_total:.2f}**")

if st.session_state.edit_id:
    st.info(f"当前正在修改订单 ID: {st.session_state.edit_id}，可以在下方手动修改总金额")
    default_total = st.session_state.edit_data.get("total", auto_total)
    custom_total = st.number_input(
        "手动修改总金额 ($)",
        min_value=0.0,
        step=0.5,
        value=float(default_total),
        key=f"total_{st.session_state.form_reset}"
    )
else:
    custom_total = auto_total

# 提交按钮
submit_label = f"✅ 确认修改订单 #{st.session_state.edit_id}" if st.session_state.edit_id else "✅ 提交并保存订单"
if st.button(submit_label, type="primary", use_container_width=True):
    if not name.strip():
        show_warning("请输入客户姓名！")
    elif not request_date.strip():
        show_warning("请输入 Request Date！")
    else:
        success, msg = save_order(
            name,
            flavor_qtys,
            request_date.strip(),
            custom_total=custom_total,
            edit_id=st.session_state.edit_id
        )
        if success:
            show_success(msg)
        else:
            show_warning(msg)

# ==================== 历史记录 ====================
st.divider()
st.subheader("📋 历史订单记录")

df = load_records()

total_revenue = df["total"].sum() if not df.empty else 0.0

st.markdown(
    f"""
    <div style="
        background-color: #fff0f3;
        border: 2px solid #d85a84;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        margin-bottom: 25px;
    ">
        <h3 style="color: #d85a84; margin: 0 0 6px 0;">💰 当前总共营业金额</h3>
        <h1 style="color: #d85a84; margin: 0; font-size: 2.2rem;">${total_revenue:,.2f}</h1>
    </div>
    """,
    unsafe_allow_html=True
)

if not df.empty:
    display_df = df.copy()
    display_df["total"] = display_df["total"].apply(lambda x: f"${x:.2f}")
    display_df.columns = ["ID", "Customer Name", "Flavors Detail", "Qty", "Total", "Request Date", "Record Time"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("#### ✏️ 修改订单")
    selected_id = st.selectbox(
        "选择要修改的订单 ID",
        options=df["id"].tolist(),
        format_func=lambda x: f"ID {x} - {df[df['id']==x]['name'].values[0]} ({df[df['id']==x]['request_date'].values[0]})"
    )

    if st.button("加载选中订单进行修改", type="secondary"):
        row = df[df["id"] == selected_id].iloc[0]
        flavors_dict = {}
        for part in row["flavors_detail"].split(","):
            if ":" in part:
                f_name, f_qty = part.split(":")
                flavors_dict[f_name.strip()] = int(f_qty.strip())

        st.session_state.edit_id = int(selected_id)
        st.session_state.edit_data = {
            "name": row["name"],
            "request_date": row["request_date"],
            "flavors": flavors_dict,
            "total": row["total"]
        }
        st.session_state.form_reset += 1
        st.rerun()

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        excel_df = df.copy()
        excel_df.columns = ["ID", "Customer Name", "Flavors Detail", "Total Quantity", "Total Price ($)", "Request Date", "Record Time"]
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            excel_df.to_excel(writer, index=False, sheet_name="Sales")
        st.download_button(
            label="📥 导出 Excel",
            data=buffer.getvalue(),
            file_name=f"Cupcake_Sales_Report_{datetime.now(TORONTO_TZ).strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with exp_col2:
        if st.button("🗑️ 清空所有记录", type="secondary", use_container_width=True):
            confirm_clear_dialog()

else:
    st.info("暂无销售记录，请先添加订单。")

st.markdown("---")
st.caption("Cozy Crumb Cake 订单管理系统 · Web Version（多伦多时区）")
