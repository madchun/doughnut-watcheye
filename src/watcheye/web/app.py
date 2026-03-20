"""Streamlit web dashboard for Watcheye."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import httpx
import streamlit as st
from sqlalchemy import select, func

from watcheye.cloner.generator import CloneGenerator
from watcheye.config import load_config, load_products
from watcheye.storage.database import get_session, init_db
from watcheye.storage.models import Brand, ContentBrief, ContentItem, ContentTag, GeneratedMedia, Tag

# --- Init ---
# On Streamlit Cloud, inject secrets as env vars so config resolver picks them up
try:
    for key in ("APIFY_TOKEN", "GEMINI_API_KEY"):
        if key in st.secrets and key not in os.environ:
            os.environ[key] = st.secrets[key]
except Exception:
    pass  # No secrets configured — running without API keys

config_path = os.environ.get("WATCHEYE_CONFIG", "config/config.yaml")
cfg = load_config(config_path)
init_db(cfg.database.url)

st.set_page_config(page_title="Watcheye — Doughnut Content Monitor", layout="wide")
st.title("🔍 Watcheye — Social Media Content Monitor")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_image(url: str) -> bytes | None:
    """Download image via server-side proxy to bypass CDN restrictions."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            return resp.content
    except Exception:
        pass
    return None


@st.cache_resource(show_spinner=False)
def get_clone_generator():
    """Cache CloneGenerator instance."""
    if not cfg.clone.gemini_api_key:
        return None
    return CloneGenerator(cfg.clone)


# --- Sidebar filters ---
st.sidebar.header("Filters")

with get_session() as session:
    brands = session.execute(select(Brand).order_by(Brand.name)).scalars().all()
    brand_names = ["All"] + [b.name for b in brands]

selected_brand = st.sidebar.selectbox("Brand", brand_names)

platform_options = ["All", "instagram", "facebook", "xiaohongshu", "x_twitter", "reddit"]
selected_platform = st.sidebar.selectbox("Platform", platform_options)

theme_options = ["All"] + [t.name for t in cfg.matrix.themes]
selected_theme = st.sidebar.selectbox("Theme", theme_options)

score_range = st.sidebar.slider("Min Score", 0.0, 100.0, 0.0)
starred_only = st.sidebar.checkbox("Starred only")

date_range = st.sidebar.date_input("Date range", value=[])

# --- Navigation: Section + Browse Mode ---
section = st.sidebar.radio("Section", ["Browse", "Briefs", "Stats"])

browse_mode = None
if section == "Browse":
    browse_mode = st.sidebar.radio("Browse Mode", ["Gallery", "Feed"])

# Brief Status filter — only shown in Briefs section
brief_status = "All"
if section == "Briefs":
    brief_status = st.sidebar.selectbox(
        "Brief Status", ["All", "draft", "approved", "rejected"], key="brief_status"
    )


def build_query():
    """Build filtered query for content items."""
    stmt = select(ContentItem).join(Brand)

    if selected_brand != "All":
        stmt = stmt.where(Brand.name == selected_brand)
    if selected_platform != "All":
        stmt = stmt.where(ContentItem.platform == selected_platform)
    if selected_theme != "All":
        stmt = stmt.where(ContentItem.detected_theme == selected_theme)
    if score_range > 0:
        stmt = stmt.where(ContentItem.final_score >= score_range)
    if starred_only:
        stmt = stmt.where(ContentItem.starred == True)  # noqa: E712
    if date_range and len(date_range) == 2:
        stmt = stmt.where(ContentItem.posted_at >= date_range[0])
        stmt = stmt.where(ContentItem.posted_at <= date_range[1])

    stmt = stmt.order_by(ContentItem.final_score.desc().nullslast())
    return stmt


# --- Clone Dialog ---
@st.dialog("Clone Content", width="large")
def clone_dialog(item_id: int):
    """In-app clone workflow dialog."""
    generator = get_clone_generator()
    if not generator:
        st.error("GEMINI_API_KEY not set. Cannot run clone workflow.")
        return

    products = load_products(cfg.clone.products_path)
    product_names = [p.name for p in products]

    with get_session() as session:
        item = session.get(ContentItem, item_id)
        if not item:
            st.error(f"Content item #{item_id} not found.")
            return

        # Step 1: Source preview
        st.markdown(f"**Source:** {item.brand.name} ({item.platform})")
        if item.media and item.media[0].original_url:
            img_data = fetch_image(item.media[0].original_url)
            if img_data:
                st.image(img_data, width=300)
        st.caption((item.caption or "")[:200])

        # Step 2: Analyze style
        is_carousel = len(item.media) > 1

        if "clone_analysis" not in st.session_state:
            with st.spinner("Analyzing style..."):
                if is_carousel:
                    images = []
                    for m in item.media:
                        if m.original_url:
                            img_bytes = fetch_image(m.original_url)
                            if img_bytes:
                                images.append(img_bytes)
                    if images:
                        analysis = generator.deep_analyze_carousel(item, images)
                    else:
                        analysis = generator.deep_analyze_style(item)
                else:
                    first_img = None
                    if item.media and item.media[0].original_url:
                        first_img = fetch_image(item.media[0].original_url)
                    analysis = generator.deep_analyze_style(item, first_img)
            st.session_state["clone_analysis"] = analysis

        analysis = st.session_state["clone_analysis"]

        # For carousel, use combined_analysis for product suggestion; for single, use analysis directly
        analysis_for_product = analysis.get("combined_analysis", analysis) if is_carousel else analysis

        # Step 3: Product suggestion
        if "clone_product_suggestion" not in st.session_state:
            with st.spinner("Suggesting product..."):
                suggestion = generator.suggest_product(analysis_for_product, products)
            st.session_state["clone_product_suggestion"] = suggestion

        suggestion = st.session_state["clone_product_suggestion"]

        st.markdown(f"**AI Suggestion:** {suggestion.get('product_name', 'N/A')}")
        st.caption(suggestion.get("reason", ""))

        # Override options
        override_options = ["Use AI suggestion"] + product_names
        user_override = st.selectbox("Override product", override_options, key="clone_product_override")
        custom_series = st.text_input("Or enter custom collection/series name", key="clone_custom_series")

        # Resolve product
        if custom_series:
            product = {"product_name": custom_series, "reason": "User selected"}
        elif user_override != "Use AI suggestion":
            product = {"product_name": user_override, "reason": "User selected"}
        else:
            product = suggestion

        st.markdown(f"**Selected product:** {product['product_name']}")

        # Step 4: Generate
        if st.button("Generate Content", type="primary", key="clone_generate_btn"):
            with st.spinner("Generating caption..."):
                caption_data = generator.generate_final_caption(item, analysis_for_product, product)

            media_count = len(item.media) if item.media else 1

            # Save brief
            brief = ContentBrief(
                source_content_id=item.id,
                style_analysis=analysis_for_product,
                deep_analysis=analysis,
                headline=caption_data.get("headline", ""),
                caption_draft=caption_data.get("caption", ""),
                suggested_post_type=item.post_type or "image",
                suggested_theme=item.detected_theme,
                slide_count=media_count,
                visual_direction=analysis_for_product.get("image_style", ""),
                cta_suggestion=caption_data.get("cta", ""),
                hashtag_suggestions=caption_data.get("hashtags", ""),
                suggested_product=product.get("product_name", ""),
                status="draft",
            )
            session.add(brief)
            session.flush()

            # Generate images
            brief_dir = Path("media/generated") / str(brief.id)
            brief_dir.mkdir(parents=True, exist_ok=True)

            product_name = product.get("product_name", "Macaroon Classic")
            product_info = next((p for p in products if p.name == product_name), None)
            if product_info:
                product_desc = (
                    f"{product_name} ({product_info.type}, {product_info.capacity}): "
                    f"{product_info.description}"
                )
            else:
                product_desc = product_name

            for img_idx in range(media_count):
                ref_bytes = None
                if img_idx < len(item.media) and item.media[img_idx].original_url:
                    ref_bytes = fetch_image(item.media[img_idx].original_url)

                image_prompt = (
                    f"Study this reference image's composition, lighting, camera angle, and mood. "
                    f"Create a NEW product photo for Doughnut brand featuring their {product_desc}. "
                    f"Adapt the visual style and atmosphere — "
                    f"style: {analysis_for_product.get('image_style', 'lifestyle photography')}, "
                    f"color palette: {analysis_for_product.get('color_palette', 'bright and warm')}, "
                    f"vibe: {analysis_for_product.get('overall_vibe', 'aspirational lifestyle')}, "
                    f"product placement: {analysis_for_product.get('product_placement', 'hero center frame')}. "
                    f"Show the actual Doughnut product — do NOT generate luggage, suitcases, "
                    f"or products Doughnut doesn't make. Doughnut only makes bags and backpacks. "
                    f"Image {img_idx + 1} of {media_count}."
                )

                with st.spinner(f"Generating image {img_idx + 1}/{media_count}..."):
                    img_bytes = generator.generate_image(image_prompt, reference_image=ref_bytes)
                    if img_bytes:
                        img_path = brief_dir / f"image_{img_idx + 1:03d}.png"
                        img_path.write_bytes(img_bytes)
                        gen_media = GeneratedMedia(
                            brief_id=brief.id,
                            media_type="image",
                            local_path=str(img_path),
                        )
                        session.add(gen_media)

            session.commit()

            # Cleanup session state
            for key in ["clone_analysis", "clone_product_suggestion"]:
                st.session_state.pop(key, None)

            st.success(f"Brief #{brief.id} created! Switch to Briefs section to review.")


def handle_star_toggle(item, session):
    """Star toggle button for a content item."""
    star_key = f"star_{item.id}"
    if st.button(
        "⭐ Starred" if item.starred else "☆ Star",
        key=star_key,
    ):
        item.starred = not item.starred
        session.commit()
        st.rerun()


def handle_clone_button(item):
    """Clone button that opens the clone dialog."""
    clone_key = f"clone_{item.id}"
    if st.button("Clone This", key=clone_key):
        clone_dialog(item.id)


# --- Gallery View ---
if section == "Browse" and browse_mode == "Gallery":
    with get_session() as session:
        stmt = build_query().limit(60)
        items = session.execute(stmt).scalars().all()

        if not items:
            st.info("No content items found. Run `watcheye collect` first.")
        else:
            cols = st.columns(4)
            for i, item in enumerate(items):
                col = cols[i % 4]
                with col:
                    # Show thumbnail if available
                    if item.media and item.media[0].original_url:
                        img_data = fetch_image(item.media[0].original_url)
                        if img_data:
                            st.image(img_data, use_container_width=True)
                    st.markdown(f"**{item.brand.name}** · {item.platform}")
                    caption_preview = (item.caption or "")[:100]
                    st.caption(caption_preview)
                    score_display = f"Score: {item.final_score:.0f}" if item.final_score else "Unscored"
                    metrics = f"❤️ {item.likes} 💬 {item.comments}"
                    st.markdown(f"{score_display} | {metrics}")
                    st.markdown(f"[View post]({item.url})" if item.url else "")

                    # Star + Clone buttons
                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        handle_star_toggle(item, session)
                    with btn_c2:
                        handle_clone_button(item)

                    st.divider()

# --- Feed View ---
elif section == "Browse" and browse_mode == "Feed":
    with get_session() as session:
        stmt = build_query().limit(50)
        items = session.execute(stmt).scalars().all()

        if not items:
            st.info("No content items found.")
        else:
            for item in items:
                with st.container():
                    left, right = st.columns([2, 3])
                    with left:
                        if item.media and item.media[0].original_url:
                            img_data = fetch_image(item.media[0].original_url)
                            if img_data:
                                st.image(img_data, use_container_width=True)
                    with right:
                        st.subheader(f"{item.brand.name} — {item.platform}")
                        st.write(item.caption or "_(no caption)_")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Likes", f"{item.likes:,}")
                        col2.metric("Comments", f"{item.comments:,}")
                        col3.metric("Shares", f"{item.shares:,}")
                        col4.metric("Score", f"{item.final_score:.0f}" if item.final_score else "—")

                        if item.posted_at:
                            st.caption(f"Posted: {item.posted_at.strftime('%Y-%m-%d %H:%M')}")
                        if item.url:
                            st.markdown(f"[Open original post]({item.url})")

                        # Star + Clone buttons
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            handle_star_toggle(item, session)
                        with btn_c2:
                            handle_clone_button(item)

                        # Tag input
                        tag_key = f"tag_{item.id}"
                        new_tag = st.text_input("Add tag", key=tag_key, label_visibility="collapsed", placeholder="Add tag...")
                        if new_tag:
                            tag = session.query(Tag).filter_by(name=new_tag).first()
                            if not tag:
                                tag = Tag(name=new_tag)
                                session.add(tag)
                                session.flush()
                            exists = session.query(ContentTag).filter_by(
                                content_id=item.id, tag_id=tag.id
                            ).first()
                            if not exists:
                                session.add(ContentTag(content_id=item.id, tag_id=tag.id))
                                session.commit()
                                st.rerun()

                    st.divider()

# --- Briefs View ---
elif section == "Briefs":
    with get_session() as session:
        briefs_query = select(ContentBrief).order_by(ContentBrief.created_at.desc())

        if brief_status != "All":
            briefs_query = briefs_query.where(ContentBrief.status == brief_status)

        briefs = session.execute(briefs_query.limit(50)).scalars().all()

        if not briefs:
            st.info("No content briefs yet. Use Clone in Browse view or run `watcheye clone`.")
        else:
            st.subheader(f"Content Briefs ({len(briefs)})")
            for brief in briefs:
                source = brief.source_content
                with st.container():
                    left, right = st.columns([2, 3])

                    with left:
                        st.markdown(f"**Source: {source.brand.name}** ({source.platform})")
                        if source.media and source.media[0].original_url:
                            img_data = fetch_image(source.media[0].original_url)
                            if img_data:
                                st.image(img_data, use_container_width=True)
                        st.caption(source.caption or "_(no caption)_")
                        col1, col2 = st.columns(2)
                        col1.metric("Likes", f"{source.likes:,}")
                        col2.metric("Score", f"{source.final_score:.0f}" if source.final_score else "—")

                    with right:
                        status_colors = {"draft": "blue", "approved": "green", "rejected": "red"}
                        color = status_colors.get(brief.status, "gray")
                        st.markdown(f"### {brief.headline or 'Untitled Brief'}")
                        st.markdown(f":{color}[{brief.status.upper()}] · {brief.suggested_post_type or '—'} · {brief.suggested_theme or '—'}")

                        if brief.suggested_product:
                            st.markdown(f"🎒 **Product:** {brief.suggested_product}")

                        if brief.slide_count:
                            st.markdown(f"**Slides:** {brief.slide_count}")

                        # Show generated images
                        if brief.generated_media:
                            st.markdown("**Generated Images:**")
                            img_cols = st.columns(min(len(brief.generated_media), 4))
                            for gi, gm in enumerate(brief.generated_media):
                                with img_cols[gi % len(img_cols)]:
                                    import os as _os
                                    if _os.path.exists(gm.local_path):
                                        st.image(gm.local_path, use_container_width=True)
                                    else:
                                        st.caption(f"📁 {gm.local_path}")

                        # Deep analysis expander — handle carousel format
                        if brief.deep_analysis:
                            with st.expander("Deep Analysis"):
                                da = brief.deep_analysis
                                if "per_image_analyses" in da:
                                    # Carousel format: per-image tabs + combined
                                    per_img = da["per_image_analyses"]
                                    tab_names = [f"Slide {i+1}" for i in range(len(per_img))]
                                    tabs = st.tabs(tab_names)
                                    for t_idx, tab in enumerate(tabs):
                                        with tab:
                                            for k, v in per_img[t_idx].items():
                                                st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                                    # Combined analysis summary
                                    combined = da.get("combined_analysis", {})
                                    if combined:
                                        st.markdown("---")
                                        st.markdown("**Overall Carousel Analysis**")
                                        for k, v in combined.items():
                                            st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                                else:
                                    # Flat dict — legacy format
                                    for k, v in da.items():
                                        st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")

                        st.markdown("**Caption Draft:**")
                        st.text_area(
                            "Caption", value=brief.caption_draft or "", key=f"caption_{brief.id}",
                            label_visibility="collapsed", height=120,
                        )

                        if brief.visual_direction:
                            st.markdown(f"**Visual Direction:** {brief.visual_direction}")
                        if brief.cta_suggestion:
                            st.markdown(f"**CTA:** {brief.cta_suggestion}")
                        if brief.hashtag_suggestions:
                            st.markdown(f"**Hashtags:** {brief.hashtag_suggestions}")

                        # Approve / Reject
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("Approve", key=f"approve_{brief.id}", type="primary"):
                                brief.status = "approved"
                                session.commit()
                                st.rerun()
                        with btn_col2:
                            if st.button("Reject", key=f"reject_{brief.id}"):
                                brief.status = "rejected"
                                session.commit()
                                st.rerun()

                        # Editor notes
                        notes = st.text_input(
                            "Editor notes", value=brief.editor_notes or "",
                            key=f"notes_{brief.id}", placeholder="Add notes...",
                        )
                        if notes != (brief.editor_notes or ""):
                            brief.editor_notes = notes
                            session.commit()

                    st.divider()

# --- Stats View ---
elif section == "Stats":
    with get_session() as session:
        st.subheader("Content by Brand & Platform")

        stmt = (
            select(
                Brand.name,
                Brand.category,
                ContentItem.platform,
                func.count(ContentItem.id).label("count"),
                func.avg(ContentItem.final_score).label("avg_score"),
                func.max(ContentItem.final_score).label("max_score"),
            )
            .join(Brand)
            .group_by(Brand.name, Brand.category, ContentItem.platform)
            .order_by(Brand.category, Brand.name)
        )
        rows = session.execute(stmt).all()

        if rows:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["Brand", "Category", "Platform", "Posts", "Avg Score", "Max Score"])
            st.dataframe(df, use_container_width=True)

            st.subheader("Top Performing Content")
            top_stmt = build_query().limit(10)
            top_items = session.execute(top_stmt).scalars().all()
            for item in top_items:
                st.markdown(
                    f"**{item.brand.name}** ({item.platform}) — "
                    f"Score: {item.final_score:.0f if item.final_score else 0} | "
                    f"❤️ {item.likes} 💬 {item.comments} | "
                    f"[Link]({item.url})"
                )
        else:
            st.info("No data yet. Run `watcheye collect` and `watcheye score` first.")

# --- Export ---
st.sidebar.markdown("---")
if st.sidebar.button("Export CSV"):
    with get_session() as session:
        stmt = build_query()
        items = session.execute(stmt).scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "brand", "platform", "account", "url", "caption",
            "likes", "comments", "shares", "saves", "views",
            "score", "theme", "posted_at", "starred",
        ])
        for item in items:
            writer.writerow([
                item.brand.name, item.platform, item.account_handle, item.url,
                (item.caption or "")[:200], item.likes, item.comments,
                item.shares, item.saves, item.views,
                item.final_score, item.detected_theme, item.posted_at, item.starred,
            ])
        st.sidebar.download_button(
            "Download CSV", output.getvalue(), "watcheye_export.csv", "text/csv"
        )

if st.sidebar.button("Export JSON"):
    with get_session() as session:
        stmt = build_query()
        items = session.execute(stmt).scalars().all()

        data = []
        for item in items:
            data.append({
                "brand": item.brand.name,
                "platform": item.platform,
                "account": item.account_handle,
                "url": item.url,
                "caption": item.caption,
                "likes": item.likes,
                "comments": item.comments,
                "shares": item.shares,
                "saves": item.saves,
                "views": item.views,
                "score": item.final_score,
                "theme": item.detected_theme,
                "posted_at": str(item.posted_at) if item.posted_at else None,
                "starred": item.starred,
            })
        st.sidebar.download_button(
            "Download JSON",
            json.dumps(data, indent=2, ensure_ascii=False),
            "watcheye_export.json",
            "application/json",
        )
