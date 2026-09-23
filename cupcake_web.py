from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import Client, create_client

# ==================== 配置区 ====================
TORONTO_TZ = ZoneInfo("America/Toronto")
PASSWORD = "0417"  # ← 这里改登录密码


# 初始化 Supabase 客户端（从 Streamlit secrets 读取云端凭证）
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


supabase = init_supabase()

# Cupcake 口味
CUPCAKE_FLAVORS = [
    "Vanilla",
    "Chocolate",
    "Strawberry",
    "Cookie Cream",
    "Salty Caremel",
    "Tiramisu",
    "Pistachio",
    "Macha",
    "Oreo",
]

# Box Cake 口味（每个 $15）
BOXCAKE_FLAVORS = [
    "Matcha Red Bean Milky Mochi",
    "Super Strawberry",
    "Hojicha Caramel Apple Creme Brulee",
    "Marshmallow Mocha",
    "Pumpkin Chestnut Milky Mochi",
]

# 页面配置
st.set_page_config(
    page_title="Cozy Crumb Cake 订单管理系统", page_icon="🧁", layout="wide"
)

st.markdown(
    """
<style>
    .stApp { background-color: #f9f5f6; }
    h1, h2, h3 { color: #d85a84 !important; }
    .stButton>button { border-radius: 8px; }
</style>
""",
    unsafe_allow_html=True,
)


# ==================== Supabase 数据库相关函数 ====================
def calculate_cupcake_total(qty):
    """Cupcake 阶梯计价：$3.5/个，6个$20，12个$40"""
    bundles_12 = qty // 12
    remainder_12 = qty % 12
    bundles_6 = remainder_12 // 6
    remainder_6 = remainder_12 % 6
    return (bundles_12 * 40.0) + (bundles_6 * 20.0) + (remainder_6 * 3.5)


def load_records():
    """从 Supabase 的 orders 表加载所有订单数据"""
    try:
        response = (
            supabase.table("orders").select("*").order("id", desc=True).execute()
        )
        data = response.data
        if data:
            return pd.DataFrame(data)
        else:
            return pd.DataFrame(
                columns=[
                    "id",
                    "name",
                    "flavors_detail",
                    "quantity",
                    "total",
                    "request_date",
                    "record_time",
                ]
            )
    except Exception as e:
        st.error(f"连接云端数据库失败: {e}")
        return pd.DataFrame(
            columns=[
                "id",
                "name",
                "flavors_detail",
                "quantity",
                "total",
                "request_date",
                "record_time",
            ]
        )


def save_order(
    name, cupcake_qtys, boxcake_qtys, request_date, custom_total=None, edit_id=None
):
    order_items = []
    total_qty = 0
    cupcake_qty = 0
    boxcake_qty = 0

    # Cupcake
    for flavor, qty in cupcake_qtys.items():
        if qty and qty > 0:
            order_items.append(f"Cupcake-{flavor}: {qty}")
            cupcake_qty += qty
            total_qty += qty

    # Box Cake
    for flavor, qty in boxcake_qtys.items():
        if qty and qty > 0:
            order_items.append(f"BoxCake-{flavor}: {qty}")
            boxcake_qty += qty
            total_qty += qty

    if total_qty == 0:
        return False, "请至少选择一个产品并输入数量！"

    flavors_detail_str = ", ".join(order_items)

    # 计算总价
    auto_total = calculate_cupcake_total(cupcake_qty) + (boxcake_qty * 15.0)

    if custom_total is not None and custom_total > 0:
        total_price = custom_total
    else:
        total_price = auto_total

    current_time = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d %H:%M:%S")

    try:
        if edit_id is None:
            # 插入新订单到 Supabase
            new_record = {
                "name": name.strip(),
                "flavors_detail": flavors_detail_str,
                "quantity": int(total_qty),
                "total": float(total_price),
                "request_date": str(request_date),
                "record_time": str(current_time),
            }
            supabase.table("orders").insert(new_record).execute()
            msg = f"订单记录成功！\n\n客户：{name}\n总数量：{total_qty} 个\n总计：${total_price:.2f}"
        else:
            # 修改 Supabase 中的订单
            updated_record = {
                "name": name.strip(),
                "flavors_detail": flavors_detail_str,
                "quantity": int(total_qty),
                "total": float(total_price),
                "request_date": str(request_date),
            }
            supabase.table("orders").update(updated_record).eq(
                "id", int(edit_id)
            ).execute()
            msg = f"订单修改成功！\n\n订单 ID：{edit_id}\n客户：{name}\n总数量：{total_qty} 个\n总计：${total_price:.2f}"

        return True, msg
    except Exception as e:
        return False, f"保存到云端数据库失败: {e}"


def delete_order(order_id):
    """删除 Supabase 中指定 ID 的订单"""
    try:
        supabase.table("orders").delete().eq("id", int(order_id)).execute()
    except Exception as e:
        st.error(f"删除失败: {e}")


def delete_all_records():
    """清空 Supabase 中的所有历史记录"""
    try:
        supabase.table("orders").delete().gt("id", 0).execute()
    except Exception as e:
        st.error(f"清空记录失败: {e}")


# ==================== 弹窗 ====================
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


@st.dialog("⚠️ 确认清空全部")
def confirm_clear_dialog():
    st.write("确定要清空**所有历史销售记录**吗？")
    st.write("此操作不可恢复！")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认清空", type="primary", use_container_width=True):
            delete_all_records()
            st.success("已清空所有历史记录！")
            st.rerun()
    with col2:
        if st.button("取消", use_container_width=True):
            st.rerun()


@st.dialog("⚠️ 确认删除订单")
def confirm_delete_dialog(order_id, customer_name):
    st.write(f"确定要删除以下订单吗？")
    st.write(f"**订单 ID：{order_id}**")
    st.write(f"**客户：{customer_name}**")
    st.write("此操作不可恢复！")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认删除", type="primary", use_container_width=True):
            delete_order(order_id)
            st.success(f"订单 ID {order_id} 已删除！")
            st.rerun()
    with col2:
        if st.button("取消", use_container_width=True):
            st.rerun()


# ==================== 登录 ====================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🧁 Cozy Crumb Cake 订单管理系统")
    st.markdown("### 请先登录")
    password = st.text_input("请输入密码", type="password", key="login_pwd")
    if st.button("登录", type="primary"):
        if password == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密码错误，请重试！")
    st.stop()


# ==================== 主界面 ====================
today_str = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")

st.title("🧁 Cozy Crumb Cake 订单管理系统")
st.caption(f"📅 Today: {today_str} （多伦多时间 · 云端同步版）")

# session_state 初始化
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "edit_data" not in st.session_state:
    st.session_state.edit_data = {}
if "form_reset" not in st.session_state:
    st.session_state.form_reset = 0

# ==================== 订单输入 ====================
st.subheader("📝 新建 / 修改订单")

col1, col2 = st.columns(2)
with col1:
    default_name = st.session_state.edit_data.get("name", "")
    name = st.text_input(
        "Customer Name",
        value=default_name,
        placeholder="请输入客户姓名",
        key=f"name_{st.session_state.form_reset}",
    )
with col2:
    default_date = st.session_state.edit_data.get("request_date", today_str)
    request_date = st.text_input(
        "Request Date",
        value=default_date,
        placeholder="例如：2026-09-14",
        key=f"date_{st.session_state.form_reset}",
    )

# ---------- Cupcake 部分 ----------
st.markdown("### 🧁 Cupcake 数量")
st.caption("$3.5/个，6个$20，12个$40")

cupcake_qtys = {}
cols = st.columns(3)
for i, flavor in enumerate(CUPCAKE_FLAVORS):
    with cols[i % 3]:
        default_qty = (
            st.session_state.edit_data.get("cupcakes", {}).get(flavor, 0)
        )
        qty = st.number_input(
            flavor,
            min_value=0,
            step=1,
            value=int(default_qty) if default_qty else 0,
            key=f"cupcake_{flavor}_{st.session_state.form_reset}",
        )
        cupcake_qtys[flavor] = qty

# ---------- Box Cake 部分 ----------
st.markdown("### 📦 Box Cake 数量")
st.caption("每个 $15")

boxcake_qtys = {}
cols2 = st.columns(3)
for i, flavor in enumerate(BOXCAKE_FLAVORS):
    with cols2[i % 3]:
        default_qty = (
            st.session_state.edit_data.get("boxcakes", {}).get(flavor, 0)
        )
        qty = st.number_input(
            flavor,
            min_value=0,
            step=1,
            value=int(default_qty) if default_qty else 0,
            key=f"boxcake_{flavor}_{st.session_state.form_reset}",
        )
        boxcake_qtys[flavor] = qty

# 计算总金额
cupcake_total_qty = sum(q for q in cupcake_qtys.values() if q)
boxcake_total_qty = sum(q for q in boxcake_qtys.values() if q)
auto_total = calculate_cupcake_total(cupcake_total_qty) + (
    boxcake_total_qty * 15.0
)

st.markdown("---")
st.markdown(f"### 💵 总金额： **${auto_total:.2f}**")
st.caption(f"Cupcake: {cupcake_total_qty} 个 + Box Cake: {boxcake_total_qty} 个")

if st.session_state.edit_id:
    st.info(
        f"当前正在修改订单 ID: {st.session_state.edit_id}，可以在下方手动修改总金额"
    )
    default_total = st.session_state.edit_data.get("total", auto_total)
    custom_total = st.number_input(
        "手动修改总金额 ($)",
        min_value=0.0,
        step=0.5,
        value=float(default_total),
        key=f"total_{st.session_state.form_reset}",
    )
else:
    custom_total = auto_total

# 提交按钮
submit_label = (
    f"✅ 确认修改订单 #{st.session_state.edit_id}"
    if st.session_state.edit_id
    else "✅ 提交并保存订单"
)
if st.button(submit_label, type="primary", use_container_width=True):
    if not name.strip():
        show_warning("请输入客户姓名！")
    elif not request_date.strip():
        show_warning("请输入 Request Date！")
    else:
        success, msg = save_order(
            name,
            cupcake_qtys,
            boxcake_qtys,
            request_date.strip(),
            custom_total=custom_total,
            edit_id=st.session_state.edit_id,
        )
        if success:
            show_success(msg)
        else:
            show_warning(msg)

# ==================== 历史记录 ====================
st.divider()
st.subheader("📋 历史订单记录")

df = load_records()
total_revenue = (
    df["total"].sum() if not df.empty and "total" in df.columns else 0.0
)

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
    unsafe_allow_html=True,
)

if not df.empty and "id" in df.columns:
    display_df = df.copy()
    display_df["total"] = display_df["total"].apply(lambda x: f"${x:.2f}")
    # 确保字段按正确顺序展示
    display_df = display_df[
        [
            "id",
            "name",
            "flavors_detail",
            "quantity",
            "total",
            "request_date",
            "record_time",
        ]
    ]
    display_df.columns = [
        "ID",
        "Customer Name",
        "Flavors Detail",
        "Qty",
        "Total",
        "Request Date",
        "Record Time",
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("#### ✏️ 修改 / 删除订单")
    selected_id = st.selectbox(
        "选择要操作的订单 ID",
        options=df["id"].tolist(),
        format_func=lambda x: f"ID {x} - {df[df['id']==x]['name'].values[0]} ({df[df['id']==x]['request_date'].values[0]})",
    )

    # 获取选中订单的客户名（用于删除确认）
    selected_row = df[df["id"] == selected_id].iloc[0]
    selected_name = selected_row["name"]

    col_edit, col_delete = st.columns(2)

    with col_edit:
        if st.button(
            "📝 加载选中订单进行修改", type="secondary", use_container_width=True
        ):
            cupcakes_dict = {}
            boxcakes_dict = {}

            for part in selected_row["flavors_detail"].split(","):
                part = part.strip()
                if ":" in part:
                    f_name, f_qty = part.split(":")
                    f_name = f_name.strip()
                    f_qty = int(f_qty.strip())
                    if f_name.startswith("Cupcake-"):
                        cupcakes_dict[
                            f_name.replace("Cupcake-", "")
                        ] = f_qty
                    elif f_name.startswith("BoxCake-"):
                        boxcakes_dict[
                            f_name.replace("BoxCake-", "")
                        ] = f_qty
                    else:
                        cupcakes_dict[f_name] = f_qty

            st.session_state.edit_id = int(selected_id)
            st.session_state.edit_data = {
                "name": selected_row["name"],
                "request_date": selected_row["request_date"],
                "cupcakes": cupcakes_dict,
                "boxcakes": boxcakes_dict,
                "total": selected_row["total"],
            }
            st.session_state.form_reset += 1
            st.rerun()

    with col_delete:
        if st.button("🗑️ 删除选中订单", type="secondary", use_container_width=True):
            confirm_delete_dialog(selected_id, selected_name)

    # 导出 & 清空全部
    st.markdown("---")
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        excel_df = display_df.copy()
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            excel_df.to_excel(writer, index=False, sheet_name="Sales")
        st.download_button(
            label="📥 导出 Excel",
            data=buffer.getvalue(),
            file_name=f"Cupcake_Sales_Report_{datetime.now(TORONTO_TZ).strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with exp_col2:
        if st.button("🗑️ 清空所有记录", type="secondary", use_container_width=True):
            confirm_clear_dialog()

else:
    st.info("暂无销售记录，请先在上方添加订单。")

st.markdown("---")
st.caption("Cozy Crumb Cake 订单管理系统 · 云端同步版（Supabase + 多伦多时区）")
