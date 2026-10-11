"""Product management operations page for GraphSupport AI (Phase 6).

Provides product catalog inspection, product lookup, customer-product linking,
and validated product registration forms.
"""

import logging

import streamlit as st

from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import EntityNotFoundError, ValidationError
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.pages.products")


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_products_page(settings: Settings) -> None:
    """Render the product management dashboard page."""
    st.subheader("📦 Product Catalog & Relationships")
    st.caption(
        "Manage hardware catalog devices, connected systems, and customer-product ownership."
    )

    service = _get_service(settings)
    if not service:
        st.warning("⚠️ **Neo4j is not connected.** Product operations are disabled.")
        return

    tab1, tab2, tab3 = st.tabs(["📋 Product Catalog", "🔗 Product Linkages", "➕ Register Product"])

    # -------------------------------------------------------------------------
    # TAB 1: Catalog
    # -------------------------------------------------------------------------
    with tab1:
        st.markdown("#### Hardware & Product Catalog")
        try:
            products = service.list_products(limit=50)
        except Exception as err:
            st.error(f"Failed to fetch products: {err}")
            return

        if not products:
            st.info("ℹ️ No catalog products found. Use the 'Register Product' tab to create one.")
        else:
            table_data = []
            for p in products:
                table_data.append(
                    {
                        "Product Name": p.name,
                        "SKU": p.sku,
                        "Category": p.category.title(),
                        "Firmware / Version": p.version,
                        "Product ID": p.id,
                    }
                )
            st.dataframe(table_data, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 2: Customer-Product Linkages
    # -------------------------------------------------------------------------
    with tab2:
        st.markdown("#### Associate Customer with Product")
        st.caption(
            "Links a customer to a hardware unit in Neo4j via `(:Customer)-[:USES]->(:Product)`."
        )

        try:
            customers = service.list_customers(limit=100)
            products = service.list_products(limit=100)
        except Exception as err:
            st.error(f"Failed to fetch entities: {err}")
            return

        if not customers or not products:
            st.warning("⚠️ Requires at least one customer and one product to create linkages.")
        else:
            cust_dict = {f"{c.name} ({c.id})": c.id for c in customers}
            prod_dict = {f"{p.name} (SKU: {p.sku})": p.id for p in products}

            with st.form("form_link_product", clear_on_submit=True):
                sel_cust_label = st.selectbox("Select Customer", options=list(cust_dict.keys()))
                sel_prod_label = st.selectbox("Select Product", options=list(prod_dict.keys()))
                link_submitted = st.form_submit_button(
                    "Link Customer to Product", use_container_width=True
                )

                if link_submitted:
                    c_id = cust_dict[sel_cust_label]
                    p_id = prod_dict[sel_prod_label]
                    try:
                        ok = service.associate_customer_with_product(
                            customer_id=c_id, product_id=p_id
                        )
                        if ok:
                            st.success("✅ Successfully linked customer to product!")
                            st.session_state.pop("cached_overview_metrics", None)
                        else:
                            st.info("Linkage already existed or was idempotent.")
                    except (ValidationError, EntityNotFoundError) as err:
                        st.warning(f"⚠️ {err}")
                    except Exception as err:
                        st.error(f"❌ Failed to link: {err}")

    # -------------------------------------------------------------------------
    # TAB 3: Register Product
    # -------------------------------------------------------------------------
    with tab3:
        st.markdown("#### Register / Upsert Hardware Product")
        with st.form("form_register_product", clear_on_submit=True):
            p_name = st.text_input("Product Name", placeholder="Smart Gateway X100")
            p_sku = st.text_input("SKU / Model Number", placeholder="GW-X100-PRO")
            p_cat = st.selectbox(
                "Category", options=["gateway", "thermostat", "sensor", "hub", "camera", "general"]
            )
            p_ver = st.text_input("Firmware Version", value="1.0.0")
            p_submit = st.form_submit_button("Save Product", use_container_width=True)

            if p_submit:
                if not p_name.strip() or not p_sku.strip():
                    st.error("Product Name and SKU are required.")
                else:
                    try:
                        prod = service.register_or_update_product(
                            name=p_name.strip(),
                            sku=p_sku.strip(),
                            category=p_cat,
                            version=p_ver.strip(),
                        )
                        st.success(f"✅ Saved **{prod.name}** (SKU: `{prod.sku}`, ID: `{prod.id}`)")
                        st.session_state.pop("cached_overview_metrics", None)
                    except ValidationError as err:
                        st.warning(f"⚠️ Validation error: {err}")
                    except Exception as err:
                        st.error(f"❌ Failed to register product: {err}")
