"""CLI entrypoint using Typer."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from watcheye.config import load_config

app = typer.Typer(name="watcheye", help="Social media content watcheye for Doughnut.")
console = Console()


@app.command()
def init(
    config_path: str = typer.Option("config/config.yaml", "--config", "-c", help="Config file path"),
):
    """Initialize database and run migrations."""
    cfg = load_config(config_path)
    from watcheye.storage.database import init_db

    console.print(f"[bold]Initializing database:[/bold] {cfg.database.url}")
    init_db(cfg.database.url)

    # Sync brands from config to DB
    from watcheye.storage.database import get_session
    from watcheye.storage.models import Brand

    with get_session() as session:
        for category, brands in cfg.matrix.brands.items():
            for brand_cfg in brands:
                existing = session.query(Brand).filter_by(name=brand_cfg.name).first()
                if not existing:
                    brand = Brand(
                        name=brand_cfg.name,
                        category=category,
                        instagram=brand_cfg.platforms.instagram or None,
                        facebook=brand_cfg.platforms.facebook or None,
                        xiaohongshu=brand_cfg.platforms.xiaohongshu or None,
                        x_twitter=brand_cfg.platforms.x_twitter or None,
                        reddit=brand_cfg.platforms.reddit or None,
                    )
                    session.add(brand)
                    console.print(f"  Added brand: {brand_cfg.name} ({category})")

    console.print("[green]Database initialized successfully.[/green]")


@app.command()
def collect(
    brand: str | None = typer.Option(None, "--brand", "-b", help="Specific brand to collect"),
    platform: str | None = typer.Option(None, "--platform", "-p", help="Specific platform"),
    config_path: str = typer.Option("config/config.yaml", "--config", "-c"),
):
    """Run content collection from social media platforms."""
    cfg = load_config(config_path)
    from watcheye.collector.apify_client import ApifyCollector
    from watcheye.storage.database import get_session, init_db
    from watcheye.storage.models import Brand, CollectionRun, ContentItem, ContentMedia

    init_db(cfg.database.url)
    apify = ApifyCollector(cfg.apify.token)

    # Build collector registry
    collectors = _build_collectors(apify, cfg)

    # Determine which brands to collect
    brands_to_collect = cfg.all_brands()
    if brand:
        match = cfg.get_brand(brand)
        if not match:
            console.print(f"[red]Brand '{brand}' not found in config.[/red]")
            raise typer.Exit(1)
        brands_to_collect = [match]

    platforms_to_collect = list(collectors.keys())
    if platform:
        if platform not in collectors:
            console.print(f"[red]Platform '{platform}' not supported.[/red]")
            raise typer.Exit(1)
        platforms_to_collect = [platform]

    with get_session() as session:
        run = CollectionRun(status="running")
        session.add(run)
        session.flush()

        total_items = 0
        errors = []

        for brand_cfg in brands_to_collect:
            db_brand = session.query(Brand).filter_by(name=brand_cfg.name).first()
            if not db_brand:
                continue

            for plat in platforms_to_collect:
                account = getattr(brand_cfg.platforms, plat, "")
                if not account:
                    continue

                collector = collectors[plat]
                limit = cfg.platforms.get(plat, None)
                max_posts = limit.max_posts_per_account if limit else 50

                console.print(f"Collecting {plat}/{account} ({brand_cfg.name})...")

                try:
                    posts = collector.collect(account, max_posts)
                    for post in posts:
                        existing = session.query(ContentItem).filter_by(
                            platform=post.platform,
                            platform_id=post.platform_id,
                        ).first()
                        if existing:
                            # Update metrics
                            existing.likes = post.likes
                            existing.comments = post.comments
                            existing.shares = post.shares
                            existing.saves = post.saves
                            existing.views = post.views
                            existing.updated_at = datetime.now(timezone.utc)
                        else:
                            item = ContentItem(
                                brand_id=db_brand.id,
                                platform=post.platform,
                                platform_id=post.platform_id,
                                account_handle=post.account_handle,
                                url=post.url,
                                caption=post.caption,
                                post_type=post.post_type,
                                posted_at=post.posted_at,
                                likes=post.likes,
                                comments=post.comments,
                                shares=post.shares,
                                saves=post.saves,
                                views=post.views,
                                followers_at_time=post.followers_at_time,
                                detected_theme=_detect_theme(post.caption, cfg),
                            )
                            session.add(item)
                            session.flush()

                            # Add media records
                            for i, url in enumerate(post.media_urls):
                                media = ContentMedia(
                                    content_id=item.id,
                                    media_type="image",
                                    original_url=url,
                                )
                                session.add(media)

                            total_items += 1

                    console.print(f"  → {len(posts)} posts collected")
                except Exception as e:
                    err_msg = f"{brand_cfg.name}/{plat}: {e}"
                    errors.append(err_msg)
                    console.print(f"  [red]Error: {e}[/red]")

        run.finished_at = datetime.now(timezone.utc)
        run.status = "completed" if not errors else "completed_with_errors"
        run.items_collected = total_items
        run.brands_collected = len(brands_to_collect)
        run.errors = "\n".join(errors) if errors else None

    console.print(f"[green]Collection complete: {total_items} new items.[/green]")


@app.command()
def score(
    config_path: str = typer.Option("config/config.yaml", "--config", "-c"),
):
    """Score or re-score all content items."""
    cfg = load_config(config_path)
    from watcheye.scorer.engagement import EngagementScorer
    from watcheye.storage.database import get_session, init_db

    init_db(cfg.database.url)
    scorer = EngagementScorer(cfg.scoring)

    with get_session() as session:
        count = scorer.score_all(session)

    console.print(f"[green]Scored {count} items.[/green]")


@app.command()
def research():
    """Generate competitor research queries."""
    from watcheye.research.competitors import generate_research_report

    report = generate_research_report()
    console.print(report)


@app.command()
def stats(
    config_path: str = typer.Option("config/config.yaml", "--config", "-c"),
):
    """Show collection statistics."""
    cfg = load_config(config_path)
    from sqlalchemy import func, select

    from watcheye.storage.database import get_session, init_db
    from watcheye.storage.models import Brand, ContentItem

    init_db(cfg.database.url)

    with get_session() as session:
        table = Table(title="Watcheye Content Stats")
        table.add_column("Brand")
        table.add_column("Platform")
        table.add_column("Posts")
        table.add_column("Avg Score")

        stmt = (
            select(
                Brand.name,
                ContentItem.platform,
                func.count(ContentItem.id),
                func.avg(ContentItem.final_score),
            )
            .join(Brand)
            .group_by(Brand.name, ContentItem.platform)
            .order_by(Brand.name)
        )
        rows = session.execute(stmt).all()
        for name, plat, count, avg_score in rows:
            table.add_row(
                name,
                plat,
                str(count),
                f"{avg_score:.1f}" if avg_score else "—",
            )

        console.print(table)


@app.command()
def seed(
    config_path: str = typer.Option("config/config.yaml", "--config", "-c", help="Config file path"),
    count: int = typer.Option(8, "--count", "-n", help="Posts per brand per platform"),
):
    """Insert fake content data for local development and testing."""
    cfg = load_config(config_path)
    from watcheye.storage.database import get_session, init_db
    from watcheye.storage.models import Brand, ContentItem, ContentMedia

    init_db(cfg.database.url)

    platforms = ["instagram", "facebook", "x_twitter", "xiaohongshu", "reddit"]
    post_types = ["image", "video", "carousel", "reel"]
    themes = [t.name for t in cfg.matrix.themes] if cfg.matrix.themes else [
        "product_showcase", "travel_adventure", "urban_lifestyle",
    ]

    captions_by_theme = {
        "product_showcase": [
            "New collection just dropped! Check out our latest design 🎒",
            "Product detail: premium water-resistant fabric for everyday carry",
            "Launching our most versatile backpack yet — perfect for work and travel",
        ],
        "travel_adventure": [
            "Adventure awaits! Our bags are ready for any journey 🌍",
            "Exploring the mountains with nothing but essentials — travel light",
            "From city streets to outdoor trails, one bag does it all",
        ],
        "urban_lifestyle": [
            "Your daily commute companion — street style meets function",
            "City life essentials: laptop, water bottle, and room to spare",
            "Everyday carry for the modern urban explorer",
        ],
        "ugc_community": [
            "Repost from @user: loving my new bag! Best unboxing ever",
            "Community spotlight: our fans show us how they carry",
            "Tagged by the community — your reviews mean the world",
        ],
        "campaign_seasonal": [
            "Limited edition collab dropping this holiday season 🎄",
            "Seasonal sale: up to 30% off our bestselling collection",
            "New campaign alert — celebrating creativity and craft",
        ],
        "behind_the_scenes": [
            "Behind the scenes: the making of our latest collection",
            "Design process — from sketch to final product in our studio",
            "The craft and story behind every stitch",
        ],
    }

    total_inserted = 0
    now = datetime.now(timezone.utc)

    with get_session() as session:
        brands = session.query(Brand).all()
        if not brands:
            console.print("[red]No brands in DB. Run 'watcheye init' first.[/red]")
            raise typer.Exit(1)

        for brand in brands:
            for plat in platforms:
                handle = getattr(brand, plat if plat != "x_twitter" else "x_twitter", None)
                if not handle:
                    handle = f"{brand.name.lower().replace(' ', '')}_{plat}"

                for i in range(count):
                    theme = random.choice(themes)
                    theme_captions = captions_by_theme.get(theme, captions_by_theme["product_showcase"])
                    caption = random.choice(theme_captions)

                    platform_id = f"fake_{brand.name.lower().replace(' ', '_')}_{plat}_{i}"
                    existing = session.query(ContentItem).filter_by(
                        platform=plat, platform_id=platform_id
                    ).first()
                    if existing:
                        continue

                    posted_at = now - timedelta(
                        hours=random.randint(1, 720),
                        minutes=random.randint(0, 59),
                    )
                    likes = random.randint(50, 15000)
                    comments_count = random.randint(5, 500)
                    shares = random.randint(0, 200)
                    saves = random.randint(0, 300)
                    views = random.randint(likes * 5, likes * 20)
                    followers = random.randint(10000, 5000000)

                    item = ContentItem(
                        brand_id=brand.id,
                        platform=plat,
                        platform_id=platform_id,
                        account_handle=handle,
                        url=f"https://example.com/{plat}/{platform_id}",
                        caption=caption,
                        post_type=random.choice(post_types),
                        posted_at=posted_at,
                        likes=likes,
                        comments=comments_count,
                        shares=shares,
                        saves=saves,
                        views=views,
                        followers_at_time=followers,
                        detected_theme=theme,
                    )
                    session.add(item)
                    session.flush()

                    media = ContentMedia(
                        content_id=item.id,
                        media_type="image",
                        original_url=f"https://picsum.photos/seed/{platform_id}/600/600",
                    )
                    session.add(media)
                    total_inserted += 1

    console.print(f"[green]Seeded {total_inserted} fake posts across {len(brands)} brands.[/green]")


@app.command()
def clone(
    brand: str | None = typer.Option(None, "--brand", "-b", help="Clone top posts from this brand"),
    top: int = typer.Option(3, "--top", "-t", help="Number of top posts to clone"),
    content_id: int | None = typer.Option(None, "--id", help="Clone a specific content item by ID"),
    config_path: str = typer.Option("config/config.yaml", "--config", "-c"),
):
    """Generate Doughnut content briefs from high-scoring competitor posts."""
    cfg = load_config(config_path)

    if not cfg.clone.gemini_api_key:
        console.print("[red]GEMINI_API_KEY not set. Export it or add to config.yaml.[/red]")
        raise typer.Exit(1)

    from watcheye.cloner.generator import CloneGenerator
    from watcheye.storage.database import get_session, init_db
    from watcheye.storage.models import Brand, ContentBrief, ContentItem

    init_db(cfg.database.url)
    generator = CloneGenerator(cfg.clone)

    with get_session() as session:
        # Find source posts
        if content_id:
            items = session.query(ContentItem).filter_by(id=content_id).all()
            if not items:
                console.print(f"[red]Content item #{content_id} not found.[/red]")
                raise typer.Exit(1)
        elif brand:
            db_brand = session.query(Brand).filter(
                Brand.name.ilike(brand)
            ).first()
            if not db_brand:
                console.print(f"[red]Brand '{brand}' not found.[/red]")
                raise typer.Exit(1)
            items = (
                session.query(ContentItem)
                .filter_by(brand_id=db_brand.id)
                .order_by(ContentItem.final_score.desc().nullslast())
                .limit(top)
                .all()
            )
        else:
            items = (
                session.query(ContentItem)
                .order_by(ContentItem.final_score.desc().nullslast())
                .limit(top)
                .all()
            )

        if not items:
            console.print("[yellow]No content items found to clone.[/yellow]")
            raise typer.Exit(0)

        console.print(f"[bold]Cloning {len(items)} post(s) → {cfg.clone.brand_name} briefs[/bold]\n")

        all_briefs = []
        for item in items:
            console.print(f"Analyzing: [cyan]{item.brand.name}[/cyan] — {(item.caption or '')[:60]}...")

            # Step 1: Analyze style
            analysis = generator.analyze_style(item)
            console.print(f"  Style: {analysis.get('tone', '?')} / {analysis.get('post_format', '?')}")

            # Step 2: Generate briefs
            briefs_data = generator.generate_briefs(
                item, analysis, count=cfg.clone.max_briefs_per_source
            )

            for brief_data in briefs_data:
                brief = ContentBrief(
                    source_content_id=item.id,
                    style_analysis=analysis,
                    headline=brief_data.get("headline"),
                    caption_draft=brief_data.get("caption_draft"),
                    suggested_post_type=brief_data.get("suggested_post_type"),
                    suggested_theme=brief_data.get("suggested_theme"),
                    slide_count=brief_data.get("slide_count"),
                    visual_direction=brief_data.get("visual_direction"),
                    cta_suggestion=brief_data.get("cta_suggestion"),
                    hashtag_suggestions=brief_data.get("hashtag_suggestions"),
                    status="draft",
                )
                session.add(brief)
                all_briefs.append(brief)

            console.print(f"  → Generated {len(briefs_data)} brief(s)\n")

        # Display results
        table = Table(title=f"Generated Content Briefs for {cfg.clone.brand_name}")
        table.add_column("#", style="dim")
        table.add_column("Source")
        table.add_column("Headline")
        table.add_column("Type")
        table.add_column("Theme")
        table.add_column("Slides")
        table.add_column("CTA")

        for i, brief in enumerate(all_briefs, 1):
            source = brief.source_content
            table.add_row(
                str(i),
                f"{source.brand.name}",
                (brief.headline or "")[:50],
                brief.suggested_post_type or "—",
                brief.suggested_theme or "—",
                str(brief.slide_count or "—"),
                (brief.cta_suggestion or "")[:40],
            )

        console.print(table)
        console.print(f"\n[green]Done! {len(all_briefs)} briefs saved to database.[/green]")


@app.command()
def wizard(
    top: int = typer.Option(5, "--top", "-t", help="Number of top posts to consider"),
    config_path: str = typer.Option("config/config.yaml", "--config", "-c"),
):
    """Interactive clone wizard — analyze top posts, suggest products, generate captions + images."""
    cfg = load_config(config_path)

    if not cfg.clone.gemini_api_key:
        console.print("[red]GEMINI_API_KEY not set. Export it or add to config.yaml.[/red]")
        raise typer.Exit(1)

    from rich.panel import Panel
    from rich.progress import Progress

    from watcheye.cloner.generator import CloneGenerator
    from watcheye.config import load_products
    from watcheye.storage.database import get_session, init_db
    from watcheye.storage.models import ContentBrief, ContentItem, GeneratedMedia

    init_db(cfg.database.url)
    generator = CloneGenerator(cfg.clone)
    products = load_products(cfg.clone.products_path)

    if not products:
        console.print("[red]No products found. Check config/products.yaml.[/red]")
        raise typer.Exit(1)

    with get_session() as session:
        # Step 1: Get top N posts by score
        items = (
            session.query(ContentItem)
            .filter(ContentItem.final_score.isnot(None))
            .order_by(ContentItem.final_score.desc())
            .limit(top)
            .all()
        )

        if not items:
            console.print("[yellow]No scored content found. Run 'watcheye score' first.[/yellow]")
            raise typer.Exit(0)

        console.print(f"\n[bold]Step 1/3: Analyzing top {len(items)} posts...[/bold]\n")

        # Step 2: Deep analyze each post + suggest product
        candidates = []
        for idx, item in enumerate(items, 1):
            console.print(f"  Analyzing #{idx}: {item.brand.name} ({item.platform})...")

            # Download first image if available
            image_bytes = None
            if item.media:
                first_media = item.media[0]
                if first_media.original_url:
                    import httpx

                    try:
                        resp = httpx.get(
                            first_media.original_url,
                            timeout=10,
                            follow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"},
                        )
                        if resp.status_code == 200:
                            image_bytes = resp.content
                    except Exception:
                        pass

            media_count = len(item.media) if item.media else 1

            # Use carousel analysis for multi-image posts
            if media_count > 1:
                carousel_images = []
                for m_item in item.media:
                    if m_item.original_url:
                        try:
                            resp = httpx.get(
                                m_item.original_url,
                                timeout=10,
                                follow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0"},
                            )
                            if resp.status_code == 200:
                                carousel_images.append(resp.content)
                        except Exception:
                            pass
                if carousel_images:
                    analysis = generator.deep_analyze_carousel(item, carousel_images)
                else:
                    analysis = generator.deep_analyze_style(item, image_bytes)
            else:
                analysis = generator.deep_analyze_style(item, image_bytes)

            # For product suggestion, use combined_analysis if carousel format
            analysis_for_product = analysis.get("combined_analysis", analysis) if "per_image_analyses" in analysis else analysis
            suggestion = generator.suggest_product(analysis_for_product, products)

            candidates.append({
                "item": item,
                "analysis": analysis,
                "analysis_for_product": analysis_for_product,
                "suggestion": suggestion,
                "media_count": media_count,
            })

        # Step 3: Display candidates
        console.print(f"\n[bold]Step 2/3: Review candidates[/bold]\n")

        for idx, cand in enumerate(candidates, 1):
            item = cand["item"]
            analysis = cand["analysis"]
            suggestion = cand["suggestion"]

            caption_preview = (item.caption or "")[:80]
            if len(item.caption or "") > 80:
                caption_preview += "..."

            display_analysis = cand["analysis_for_product"]
            body = (
                f"Caption: {caption_preview}\n"
                f"Post type: {item.post_type or 'unknown'} ({cand['media_count']} media)\n"
                f"\n"
                f"Image style: {display_analysis.get('image_style', 'n/a')}\n"
                f"Background: {display_analysis.get('background_description', 'n/a')}\n"
                f"Vibe: {display_analysis.get('overall_vibe', 'n/a')}\n"
                f"Product placement: {display_analysis.get('product_placement', 'n/a')}\n"
                f"People: {display_analysis.get('people_and_models', 'n/a')}\n"
                f"\n"
                f"\U0001f392 Suggested: {suggestion.get('product_name', 'n/a')}\n"
                f"   \"{suggestion.get('reason', '')}\""
            )

            panel = Panel(
                body,
                title=f"#{idx} {item.brand.name} ({item.platform}) — Score: {item.final_score:.0f}",
                border_style="cyan",
            )
            console.print(panel)

        # Step 4: User selection
        selection_str = typer.prompt(
            f"\nSelect posts to clone (1-{len(candidates)}, comma-separated, or 'all')"
        )

        if selection_str.strip().lower() == "all":
            selected_indices = list(range(len(candidates)))
        else:
            try:
                selected_indices = [int(s.strip()) - 1 for s in selection_str.split(",")]
                selected_indices = [i for i in selected_indices if 0 <= i < len(candidates)]
            except ValueError:
                console.print("[red]Invalid selection.[/red]")
                raise typer.Exit(1)

        if not selected_indices:
            console.print("[yellow]No posts selected.[/yellow]")
            raise typer.Exit(0)

        console.print(f"\n[bold]Step 3/3: Generating content for {len(selected_indices)} post(s)...[/bold]\n")

        # Step 5: Generate caption + images for each selected post
        results = []
        media_base = Path("media/generated")

        with Progress(console=console) as progress:
            for sel_idx in selected_indices:
                cand = candidates[sel_idx]
                item = cand["item"]
                analysis = cand["analysis"]
                analysis_for_product = cand["analysis_for_product"]
                suggestion = cand["suggestion"]
                media_count = cand["media_count"]

                task_label = f"#{sel_idx + 1} {item.brand.name}"
                task = progress.add_task(task_label, total=1 + media_count)

                # Generate final caption
                caption_data = generator.generate_final_caption(item, analysis_for_product, suggestion)
                progress.advance(task)

                # Save ContentBrief
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
                    suggested_product=suggestion.get("product_name", ""),
                    status="draft",
                )
                session.add(brief)
                session.flush()

                # Generate images
                brief_dir = media_base / str(brief.id)
                brief_dir.mkdir(parents=True, exist_ok=True)

                product_name = suggestion.get("product_name", "Macaroon Classic")
                # Look up full product info from catalog
                product_info = next((p for p in products if p.name == product_name), None)
                if product_info:
                    product_desc = (
                        f"{product_name} ({product_info.type}, {product_info.capacity}): "
                        f"{product_info.description}"
                    )
                else:
                    product_desc = product_name

                for img_idx in range(media_count):
                    # Download corresponding original image as reference
                    ref_bytes = None
                    if img_idx < len(item.media) and item.media[img_idx].original_url:
                        import httpx as _httpx

                        try:
                            resp = _httpx.get(
                                item.media[img_idx].original_url,
                                timeout=10,
                                follow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0"},
                            )
                            if resp.status_code == 200:
                                ref_bytes = resp.content
                        except Exception:
                            pass

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

                    # Rate limit: pause between image generation calls
                    if img_idx > 0:
                        import time
                        time.sleep(10)

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

                    progress.advance(task)

                results.append({
                    "brief": brief,
                    "caption_data": caption_data,
                    "images_dir": str(brief_dir),
                    "images_generated": len(list(brief_dir.glob("*.png"))),
                })

        # Step 6: Display results
        console.print()
        result_table = Table(title="Generated Content")
        result_table.add_column("#", style="dim")
        result_table.add_column("Source")
        result_table.add_column("Product")
        result_table.add_column("Headline")
        result_table.add_column("Images")
        result_table.add_column("Path")

        for i, res in enumerate(results, 1):
            brief = res["brief"]
            source = brief.source_content
            result_table.add_row(
                str(i),
                f"{source.brand.name}",
                brief.suggested_product or "—",
                (brief.headline or "")[:50],
                str(res["images_generated"]),
                res["images_dir"],
            )

        console.print(result_table)
        console.print(f"\n[green]Done! {len(results)} brief(s) with images saved.[/green]")


@app.command()
def serve(
    config_path: str = typer.Option("config/config.yaml", "--config", "-c"),
    port: int = typer.Option(8501, "--port"),
):
    """Launch Streamlit web viewer."""
    import subprocess
    import sys

    web_app = Path(__file__).parent / "web" / "app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(web_app), "--server.port", str(port)],
        env={**__import__("os").environ, "WATCHEYE_CONFIG": config_path},
    )


def _build_collectors(apify, cfg):
    """Build dict of platform -> collector instances."""
    from watcheye.collector.facebook import FacebookCollector
    from watcheye.collector.instagram import InstagramCollector
    from watcheye.collector.reddit import RedditCollector
    from watcheye.collector.x_twitter import XTwitterCollector
    from watcheye.collector.xiaohongshu import XiaohongshuCollector

    collectors = {}
    for plat, settings in cfg.platforms.items():
        if plat == "instagram":
            collectors[plat] = InstagramCollector(apify, settings.apify_actor)
        elif plat == "facebook":
            collectors[plat] = FacebookCollector(apify, settings.apify_actor)
        elif plat == "xiaohongshu":
            collectors[plat] = XiaohongshuCollector(apify, settings.apify_actor)
        elif plat == "x_twitter":
            collectors[plat] = XTwitterCollector(apify, settings.apify_actor)
        elif plat == "reddit":
            collectors[plat] = RedditCollector(apify, settings.apify_actor)
    return collectors


def _detect_theme(caption: str, cfg) -> str | None:
    """Simple keyword-based theme detection."""
    if not caption:
        return None
    caption_lower = caption.lower()
    best_theme = None
    best_count = 0
    for theme in cfg.matrix.themes:
        count = sum(1 for kw in theme.keywords if kw.lower() in caption_lower)
        if count > best_count:
            best_count = count
            best_theme = theme.name
    return best_theme


if __name__ == "__main__":
    app()
